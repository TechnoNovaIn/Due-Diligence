"""Cross-document verification engine.

Documents are analysed collectively.  Every detector states what the evidence
shows, cites it, and stops there: a name that matches across two deeds is
recorded as *documented*, never as *verified ownership*; the absence of a
litigation document is recorded as *not checked*, never as *no litigation*.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..enums import FindingCategory, Severity, VerificationStatus
from . import normalize as nz
from .context import (
    AnalysisResult,
    CaseContext,
    DocFacts,
    Evidence,
    FieldValue,
    OwnershipStep,
    ProposedFinding,
)
from .knowledge import (
    AGRICULTURAL_INDICATOR_TYPES,
    MORTGAGE_RELEASE_TYPES,
    MORTGAGE_TYPES,
    TITLE_TRANSFER_TYPES,
    doc_label,
)

#: Area differences below this are treated as rounding / measurement conversion.
AREA_TOLERANCE_PCT = 2.0
AREA_MATERIAL_PCT = 5.0

#: Documents that move title from one named person to another.
TRANSFER_ROLE_BY_TYPE = {
    "sale_deed": ("party_seller", "party_buyer", "Sale"),
    "title_deed": ("party_seller", "party_buyer", "Transfer"),
    "conveyance_deed": ("party_seller", "party_buyer", "Conveyance"),
    "apartment_deed": ("party_seller", "party_buyer", "Apartment conveyance"),
    "gift_deed": ("party_donor", "party_buyer", "Gift"),
    "mother_deed": ("party_seller", "party_buyer", "Earlier transfer"),
}

#: Documents that divide, confirm or devolve rights among several parties. They
#: do not have a transferor and a transferee, and which party received *this*
#: property cannot be read off the party roles - it depends on the schedules.
ALLOCATION_TYPES = {
    "partition_deed": "Partition among co-owners",
    "settlement_deed": "Settlement",
    "release_deed": "Release / relinquishment",
    "exchange_deed": "Exchange",
    "inheritance_document": "Inheritance / succession",
    "court_order_ownership": "Court order",
}

PARTY_KEYS = ("party_seller", "party_buyer", "party_donor", "party_executant", "owner_name")


def verify(ctx: CaseContext) -> AnalysisResult:
    result = AnalysisResult()
    _detect_conditions(ctx, result)
    _verify_ownership(ctx, result)
    _verify_property_identity(ctx, result)
    _verify_encumbrance(ctx, result)
    _verify_land_use(ctx, result)
    _verify_legal(ctx, result)
    _verify_document_integrity(ctx, result)
    _verify_process(ctx, result)
    return result


# ---------------------------------------------------------------------------
# Conditions that drive the dynamic requirement checklist
# ---------------------------------------------------------------------------
def _detect_conditions(ctx: CaseContext, result: AnalysisResult) -> None:
    cond = result.conditions
    prop_type = ctx.case.property_type

    if ctx.has_type(*AGRICULTURAL_INDICATOR_TYPES):
        cond.add("agricultural_origin")
    for v in ctx.values("land_classification"):
        if re.search(r"agric|dry|wet|garden|khushki|bagayat", (v.norm or ""), re.IGNORECASE):
            cond.add("agricultural_origin")
        if re.search(r"convert|non[\s\-]?agric|residential|commercial|industrial", (v.norm or ""), re.IGNORECASE):
            cond.add("converted_land")
    if prop_type in ("agricultural_land", "undeveloped_land"):
        cond.add("agricultural_origin")

    for v in ctx.values("survey_number"):
        if re.search(r"[/\-]", nz.normalize_survey_number(v.display)):
            cond.add("subdivided_survey_number")
    if ctx.case.subdivision_number:
        cond.add("subdivided_survey_number")

    if ctx.has_type("inheritance_document", "legal_heir_certificate", "succession_certificate",
                    "partition_deed", "court_order_ownership"):
        cond.add("inheritance_in_chain")

    if ctx.has_type("power_of_attorney"):
        cond.add("poa_used")
    if ctx.has_type(*MORTGAGE_TYPES) or ctx.tagged("mortgage_status", "mortgage_indicated"):
        cond.add("mortgage_detected")
    if ctx.tagged("restriction_mention", "grant_land_indicator"):
        cond.add("grant_land_indicator")
    if ctx.tagged("restriction_mention", "tenancy_indicator"):
        cond.add("tenancy_indicator")

    if prop_type in ("apartment", "under_construction", "independent_house", "commercial", "industrial"):
        cond.add("built_property")
    if prop_type in ("apartment", "independent_house", "commercial") and prop_type != "under_construction":
        cond.add("completed_construction")
    if ctx.has_type("occupancy_certificate", "completion_certificate"):
        cond.add("completed_construction")
    if prop_type in ("residential_plot",) or ctx.has_type("approved_building_plan"):
        cond.add("layout_property")
    if prop_type in ("apartment", "under_construction") or ctx.has_type("rera_registration", "builder_agreement"):
        cond.add("rera_applicable")


# ---------------------------------------------------------------------------
# A. Ownership and title chain
# ---------------------------------------------------------------------------
@dataclass
class _Step:
    doc: DocFacts
    from_owner: Optional[str]
    to_owner: Optional[str]
    label: str
    when: Optional[date]
    directional: bool
    parties: List[str]
    #: True when the document is a transfer whose party roles could not be read,
    #: as against an allocation that names parties without directing a transfer.
    roles_unread: bool = False


def _transfer_steps(ctx: CaseContext) -> List[_Step]:
    """Build the chronology, keeping directional transfers separate from allocations."""
    steps: List[_Step] = []
    for doc in ctx.by_type(*TITLE_TRANSFER_TYPES):
        if doc.doc_type in ALLOCATION_TYPES:
            parties: List[str] = []
            for key in PARTY_KEYS:
                for v in doc.all(key):
                    name = nz.normalize_name(v.display)
                    if name and name not in parties:
                        parties.append(name)
            if not parties:
                continue
            steps.append(_Step(doc=doc, from_owner=None, to_owner=None,
                               label=ALLOCATION_TYPES[doc.doc_type], when=doc.best_date,
                               directional=False, parties=parties))
            continue

        from_key, to_key, label = TRANSFER_ROLE_BY_TYPE.get(
            doc.doc_type, ("party_seller", "party_buyer", "Transfer"))
        from_owner = doc.value(from_key) if from_key else None
        to_owner = doc.value(to_key) if to_key else None
        if not from_owner and not to_owner:
            # The roles could not be read - on a Kaveri deed the labelled cover
            # sheet is a stamped form that scans badly - but the parties are
            # often named in the body. Listing them, with the roles openly
            # unresolved, is worth more than dropping the transfer from the
            # chain and reporting that no transfer document exists.
            named: List[str] = []
            for key in PARTY_KEYS:
                for v in doc.all(key):
                    name = nz.normalize_name(v.display)
                    if name and name not in named:
                        named.append(name)
            if not named:
                continue
            steps.append(_Step(doc=doc, from_owner=None, to_owner=None,
                               label=TRANSFER_ROLE_BY_TYPE.get(doc.doc_type, (None, None, "Transfer"))[2],
                               when=doc.best_date, directional=False, parties=named,
                               roles_unread=True))
            continue
        steps.append(_Step(doc=doc, from_owner=from_owner, to_owner=to_owner, label=label,
                           when=doc.best_date, directional=True,
                           parties=[n for n in (from_owner, to_owner) if n]))
    steps.sort(key=lambda s: (s.when or date(1900, 1, 1)))
    return steps


def _verify_ownership(ctx: CaseContext, result: AnalysisResult) -> None:
    steps = _transfer_steps(ctx)
    claimed = ctx.case.claimed_owner

    seq = 0
    previous_to: Optional[str] = None
    previous_doc: Optional[DocFacts] = None
    for step in steps:
        seq += 1
        gap = False
        notes = None

        if not step.directional:
            # An allocation document names several parties but does not say, from the
            # party roles alone, which of them took this particular property.
            if step.roles_unread:
                notes = (
                    "This document names {}, but which of them transferred the property and "
                    "which acquired it could not be read from the copy supplied. The roles "
                    "must be confirmed from the document itself."
                ).format(", ".join(step.parties[:5]))
            else:
                notes = (
                    "This document divides or confirms rights among {}. Which party the subject "
                    "property was allotted to cannot be read from the party roles and must be "
                    "confirmed from the schedules in the document."
                ).format(", ".join(step.parties[:5]))
            if previous_to and not any(nz.names_match(previous_to, p) for p in step.parties):
                notes += (" The person who held the property immediately before this document, {}, "
                          "is not named as a party.").format(nz.normalize_name(previous_to))
            result.ownership.append(OwnershipStep(
                sequence=seq, from_owner=None, to_owner=None, transfer_type=step.label,
                transfer_date=step.when.isoformat() if step.when else None,
                document_id=step.doc.id, document_name=step.doc.filename,
                registration_ref=step.doc.value("registration_number"),
                verification_status=VerificationStatus.UNVERIFIED.value,
                gap_before=False, notes=notes,
            ))
            continue

        from_owner, to_owner = step.from_owner, step.to_owner
        if previous_to and from_owner and not nz.names_match(previous_to, from_owner):
            # An allocation document in between may explain the change of hands.
            explained_by = next(
                (s for s in steps
                 if not s.directional and s.when and step.when and s.when <= step.when
                 and any(nz.names_match(from_owner, p) for p in s.parties)),
                None,
            )
            if explained_by is not None:
                notes = ("The transferor is named as a party to {} dated {}; that document may be "
                         "how the property came to this transferor, but the allotment itself has "
                         "not been confirmed.").format(
                    explained_by.doc.filename,
                    nz.format_date(explained_by.when.isoformat()) if explained_by.when else "an unstated date")
            else:
                gap = True
                notes = ("The transferor named here does not match the person who acquired the "
                         "property in the preceding document on record.")
                fp = ProposedFinding.make_fingerprint(
                    "ownership_chain_break", nz.normalize_name(previous_to), nz.normalize_name(from_owner))
                result.findings.append(ProposedFinding(
                    fingerprint=fp,
                    category=FindingCategory.OWNERSHIP.value,
                    severity=Severity.HIGH.value,
                    title="Break in the ownership chain between {} and {}".format(
                        nz.normalize_name(previous_to), nz.normalize_name(from_owner)),
                    description=(
                        "The preceding document on record shows the property vesting in {prev}. The next "
                        "document in date order, {doc}, is executed by {cur}. No document on record "
                        "explains how the property moved from {prev} to {cur}."
                    ).format(prev=nz.normalize_name(previous_to), cur=nz.normalize_name(from_owner),
                             doc=step.doc.filename),
                    consequence=("If the intervening transfer was defective or never took place, the "
                                 "present seller may not hold transferable title."),
                    recommended_action=("Obtain the document that transferred the property from {} to {} "
                                        "(sale, gift, partition, settlement, inheritance or a court "
                                        "order).").format(nz.normalize_name(previous_to),
                                                          nz.normalize_name(from_owner)),
                    required_documents=["Document evidencing the transfer from {} to {}".format(
                        nz.normalize_name(previous_to), nz.normalize_name(from_owner))],
                    confidence=0.75, confirmed=True, requires_legal_review=True,
                    verification_status=VerificationStatus.CONFLICTING.value,
                    evidence=[e for e in (
                        Evidence.from_doc(previous_doc, "Shows the property vesting in {}.".format(
                            nz.normalize_name(previous_to))) if previous_doc else None,
                        Evidence.from_doc(step.doc, "Executed by {} as transferor.".format(
                            nz.normalize_name(from_owner))),
                    ) if e is not None],
                    detector="ownership_chain_break",
                ))

        result.ownership.append(OwnershipStep(
            sequence=seq, from_owner=from_owner, to_owner=to_owner, transfer_type=step.label,
            transfer_date=step.when.isoformat() if step.when else None,
            document_id=step.doc.id, document_name=step.doc.filename,
            registration_ref=step.doc.value("registration_number"),
            verification_status=VerificationStatus.DOCUMENTED.value,
            gap_before=gap, notes=notes,
        ))
        if to_owner:
            previous_to, previous_doc = to_owner, step.doc

    # -- the chain must reach back far enough -----------------------------
    if steps:
        earliest = steps[0]
        result.conditions.add("has_title_document")
        if earliest.when:
            years = (nz.today() - earliest.when).days / 365.25
            if years < ctx.title_lookback_years:
                fp = ProposedFinding.make_fingerprint("chain_coverage", earliest.doc.id)
                result.findings.append(ProposedFinding(
                    fingerprint=fp,
                    category=FindingCategory.OWNERSHIP.value,
                    severity=Severity.MEDIUM.value,
                    title="Title chain on record covers about {:.0f} years, short of the {}-year review period".format(
                        years, ctx.title_lookback_years),
                    description=(
                        "The earliest title document on record is {doc} dated {when}. Title is "
                        "customarily traced for about {need} years in this jurisdiction; about "
                        "{have:.0f} years are currently documented. The documents preceding {when} "
                        "have not been supplied."
                    ).format(doc=earliest.doc.filename,
                             when=nz.format_date(earliest.when.isoformat()),
                             need=ctx.title_lookback_years, have=years),
                    consequence=("A defect in an earlier, unexamined transfer would not be visible "
                                 "from the documents on record."),
                    recommended_action="Collect the parent deeds preceding {} and continue the chain backwards.".format(
                        nz.format_date(earliest.when.isoformat())),
                    required_documents=["Parent deeds predating {}".format(
                        nz.format_date(earliest.when.isoformat()))],
                    confidence=0.8, confirmed=True, requires_legal_review=False,
                    verification_status=VerificationStatus.DOCUMENTED.value,
                    evidence=[Evidence.from_doc(earliest.doc,
                                                "Earliest title document currently on record.")],
                    detector="chain_coverage",
                ))
        if earliest.from_owner:
            result.notes.append(
                "The chain on record begins with {} as transferor; how that person acquired the "
                "property is not documented in the supplied material.".format(
                    nz.normalize_name(earliest.from_owner))
            )
    else:
        result.conditions.add("no_title_document")

    _detect_missing_parent_deeds(ctx, result)

    directional = [s for s in steps if s.directional]
    if claimed and directional:
        last_to = next((s.to_owner for s in reversed(directional) if s.to_owner), None)
        if last_to and not nz.names_match(claimed, last_to):
            fp = ProposedFinding.make_fingerprint("claimed_owner_mismatch",
                                                  nz.normalize_name(claimed), nz.normalize_name(last_to))
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.OWNERSHIP.value,
                severity=Severity.HIGH.value,
                title="Claimed owner differs from the person shown as acquiring the property",
                description=(
                    "The case records {claimed} as the current owner, but the latest transfer document "
                    "on record shows the property being acquired by {actual}."
                ).format(claimed=nz.normalize_name(claimed), actual=nz.normalize_name(last_to)),
                consequence="The person proposing to transfer may not be the titleholder of record.",
                recommended_action=("Reconcile the names, or obtain the document under which {} "
                                    "acquired the property.").format(nz.normalize_name(claimed)),
                required_documents=["Document showing acquisition by {}".format(nz.normalize_name(claimed))],
                confidence=0.7, confirmed=True, requires_legal_review=True,
                verification_status=VerificationStatus.CONFLICTING.value,
                evidence=[Evidence.from_doc(directional[-1].doc, "Latest transfer document on record.")],
                detector="claimed_owner_mismatch",
            ))

    _compare_record_holder(ctx, result, directional)

    if ctx.case.seller_name and directional:
        last_to = next((s.to_owner for s in reversed(directional) if s.to_owner), None)
        if last_to and not nz.names_match(ctx.case.seller_name, last_to) and not (
            claimed and nz.names_match(ctx.case.seller_name, claimed)
        ):
            fp = ProposedFinding.make_fingerprint("seller_not_titleholder",
                                                  nz.normalize_name(ctx.case.seller_name))
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.OWNERSHIP.value,
                severity=Severity.HIGH.value,
                title="Proposed seller is not the titleholder shown in the documents",
                description=(
                    "The case names {seller} as the seller, but the documents show the property vesting "
                    "in {holder}. No document on record establishes {seller}'s authority to transfer."
                ).format(seller=nz.normalize_name(ctx.case.seller_name),
                         holder=nz.normalize_name(last_to)),
                consequence="A transfer by a person without title or authority may be void against the true owner.",
                recommended_action=("Obtain the document establishing the seller's title, or a registered "
                                    "power of attorney from the titleholder."),
                required_documents=["Title document in the seller's name",
                                    "Registered power of attorney (if acting for the owner)"],
                confidence=0.65, confirmed=False, requires_legal_review=True,
                verification_status=VerificationStatus.UNVERIFIED.value,
                evidence=[Evidence.from_doc(directional[-1].doc, "Latest transfer document on record.")],
                detector="seller_not_titleholder",
            ))


def _detect_missing_parent_deeds(ctx: CaseContext, result: AnalysisResult) -> None:
    """A deed that recites an earlier deed creates an obligation to produce it."""
    available_types = ctx.doc_types_present
    for ref in ctx.values("parent_deed_reference"):
        text = (ref.norm or ref.raw or "")
        lowered = text.lower()
        deed_type = None
        for key, phrase in (
            ("partition_deed", "partition deed"), ("gift_deed", "gift deed"),
            ("settlement_deed", "settlement deed"), ("release_deed", "release deed"),
            ("sale_deed", "sale deed"), ("mother_deed", "mother deed"),
            ("inheritance_document", "will"), ("court_order_ownership", "decree"),
            ("exchange_deed", "exchange deed"),
        ):
            if phrase in lowered:
                deed_type = key
                break
        if deed_type is None:
            continue
        ref_date = nz.parse_date(text)
        ref_number_m = re.search(r"(?:no\.?|number)\s*([A-Za-z0-9\-/]{2,30})", text, re.IGNORECASE)
        ref_number = ref_number_m.group(1) if ref_number_m else None

        if deed_type in available_types:
            candidates = ctx.by_type(deed_type)
            matched = False
            for cand in candidates:
                if ref_date and cand.best_date == ref_date:
                    matched = True
                    break
                if ref_number and any(
                    nz.normalize_identifier(v.display) == nz.normalize_identifier(ref_number)
                    for v in cand.all("registration_number") + cand.all("parent_registration_number")
                ):
                    matched = True
                    break
            if matched or (not ref_date and not ref_number):
                continue

        descriptor = doc_label(deed_type)
        if ref_date:
            descriptor += " dated {}".format(nz.format_date(ref_date.isoformat()))
        if ref_number:
            descriptor += " (document no. {})".format(ref_number)

        fp = ProposedFinding.make_fingerprint("missing_parent_deed", deed_type,
                                              ref_date.isoformat() if ref_date else "", ref_number or "")
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.OWNERSHIP.value,
            severity=Severity.HIGH.value,
            title="Referenced {} has not been supplied".format(doc_label(deed_type)),
            description=(
                "{source} recites that the transferor derived title under a {descriptor}. That document "
                "is not present in this case file, so the transfer it records cannot be examined."
            ).format(source=ref.document_name, descriptor=descriptor),
            consequence=("The earlier transfer cannot be checked for validity, extent, shares or "
                         "conditions, leaving a gap in the title chain."),
            recommended_action="Obtain a certified copy of the {} from the seller or the Sub-Registrar.".format(descriptor),
            required_documents=[descriptor],
            confidence=0.85, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.DOCUMENTED.value,
            evidence=[Evidence.from_value(ref, "Reference to the parent document in {}.".format(ref.document_name))],
            detector="missing_parent_deed",
        ))
        result.conditions.add("parent_deed_missing")


def _compare_record_holder(ctx: CaseContext, result: AnalysisResult, steps) -> None:
    """Revenue/municipal records should name the same person as the deeds."""
    record_docs = ctx.by_type("rtc_pahani", "khata_certificate", "khata_extract",
                              "mutation_extract", "property_tax_receipt")
    if not record_docs or not steps:
        return
    title_holder = next((s.to_owner for s in reversed(steps) if s.to_owner), None)
    if not title_holder:
        return
    for doc in record_docs:
        holder = doc.first("owner_name")
        if not holder or not holder.display:
            continue
        if nz.names_match(title_holder, holder.display):
            continue
        similarity = nz.name_similarity(title_holder, holder.display)
        severity = Severity.MEDIUM.value if similarity >= 60 else Severity.HIGH.value
        fp = ProposedFinding.make_fingerprint("record_holder_mismatch", doc.id,
                                              nz.normalize_name(holder.display))
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.OWNERSHIP.value,
            severity=severity,
            title="{} stands in a different name from the title documents".format(doc.label),
            description=(
                "{doc} records {record} as the holder, while the title documents show the property "
                "vesting in {title}. The name similarity is {sim}%."
            ).format(doc=doc.filename, record=nz.normalize_name(holder.display),
                     title=nz.normalize_name(title_holder), sim=similarity),
            consequence=("The revenue or municipal record may not have been mutated after the registered "
                         "transfer, or the record may relate to a different person or property."),
            recommended_action=("Obtain the mutation record for the transfer and a current extract, and "
                                "reconcile the names."),
            required_documents=["Mutation register extract for the latest transfer", "Current revenue/khata extract"],
            confidence=0.7, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.CONFLICTING.value,
            evidence=[Evidence.from_value(holder, "Holder named in {}.".format(doc.filename))],
            detector="record_holder_mismatch",
        ))
        result.conditions.add("mutation_pending")


# ---------------------------------------------------------------------------
# B. Property identity
# ---------------------------------------------------------------------------
def _grouped(values: Sequence[FieldValue], normaliser) -> Dict[str, List[FieldValue]]:
    groups: Dict[str, List[FieldValue]] = defaultdict(list)
    for v in values:
        key = normaliser(v.display)
        if key:
            groups[key].append(v)
    return groups


def _verify_property_identity(ctx: CaseContext, result: AnalysisResult) -> None:
    _compare_identifier(ctx, result, "survey_number", "Survey number", nz.normalize_survey_number,
                        Severity.HIGH.value, allow_subdivision=True)
    _compare_identifier(ctx, result, "khata_number", "Khata number", nz.normalize_identifier, Severity.MEDIUM.value)
    _compare_identifier(ctx, result, "plot_number", "Plot number", nz.normalize_identifier, Severity.MEDIUM.value)
    _compare_identifier(ctx, result, "flat_number", "Flat / unit number", nz.normalize_identifier, Severity.MEDIUM.value)
    _compare_identifier(ctx, result, "village", "Village", lambda v: nz.normalize_name(v).lower(),
                        Severity.MEDIUM.value, across_scripts=True)
    _compare_identifier(ctx, result, "taluk", "Taluk", lambda v: nz.normalize_name(v).lower(),
                        Severity.MEDIUM.value, across_scripts=True)
    _compare_area(ctx, result)
    _compare_boundaries(ctx, result)
    _compare_with_case_record(ctx, result)


def _script_of(text: str) -> str:
    """Which script a value is written in, for values that may be in either."""
    for ch in text:
        if "\u0c80" <= ch <= "\u0cff":
            return "kannada"
    return "latin" if any(ch.isalpha() for ch in text) else "other"


def _absorbs(longer: str, shorter: str) -> bool:
    """True when one value says the same thing as another, more fully.

    "Kasaba North" and "North" are one hobli recorded twice, the second time
    incompletely. Only a strict token subset counts: values that merely look
    alike are left to disagree, because a reviewer shown a false conflict loses
    an hour, while one not shown a real one may buy the wrong land.
    """
    a = {t for t in re.split(r"[\s,./-]+", longer.casefold()) if t}
    b = {t for t in re.split(r"[\s,./-]+", shorter.casefold()) if t}
    return bool(a) and bool(b) and b < a


def _merge_contained(names: List[str]) -> List[str]:
    """Drop values wholly contained in a longer one from the same script."""
    kept = []
    for name in sorted(names, key=len, reverse=True):
        if not any(_absorbs(bigger, name) for bigger in kept):
            kept.append(name)
    return kept



def _conflicting_within_script(groups: dict) -> dict:
    """The values that genuinely disagree, which means disagreeing in one script.

    A Kannada document calls the village \u0c85\u0cb0\u0c95\u0cc6\u0cb0\u0cc6 and an English one calls it
    Arakere. Establishing that those are the same place needs transliteration,
    which this system does not do - but neither can it call them a conflict,
    because it has no basis for saying they differ. Only values written in the
    same script are compared, so a reviewer is shown a real discrepancy rather
    than a translation.
    """
    by_script = {}
    for group in groups:
        by_script.setdefault(_script_of(group), []).append(group)
    conflicting = {}
    for names in by_script.values():
        names = _merge_contained(names)
        if len(names) > 1:
            for name in names:
                conflicting[name] = groups[name]
    return conflicting


def _compare_identifier(ctx: CaseContext, result: AnalysisResult, key: str, label: str,
                        normaliser, severity: str, allow_subdivision: bool = False,
                        across_scripts: bool = False) -> None:
    values = ctx.values(key)
    groups = _grouped(values, normaliser)
    if across_scripts and len(groups) > 1:
        conflicting = _conflicting_within_script(groups)
        if conflicting:
            # Carry on with the values that actually disagree, leaving the other
            # script's rendering out of a conflict it is not party to.
            groups = conflicting
        else:
            result.comparisons.append({
                "field": key, "label": label,
                "values": [
                    {"value": group, "documents": sorted({v.document_name for v in vs}),
                     "pages": sorted({v.page_no for v in vs if v.page_no})}
                    for group, vs in sorted(groups.items())
                ],
                "consistent": None,
                "note": ("The documents give this in more than one script. Whether they name "
                         "the same place has not been established; no transliteration was "
                         "performed."),
            })
            return
    result.comparisons.append({
        "field": key, "label": label,
        "values": [
            {"value": group, "documents": sorted({v.document_name for v in vs}),
             "pages": sorted({v.page_no for v in vs if v.page_no})}
            for group, vs in sorted(groups.items())
        ],
        "consistent": len(groups) <= 1,
    })
    if len(groups) <= 1:
        return

    distinct = sorted(groups.keys())
    subdivision_related = False
    if allow_subdivision:
        roots = {nz.survey_number_root(g) for g in distinct}
        subdivision_related = len(roots) == 1

    if subdivision_related:
        fp = ProposedFinding.make_fingerprint("identity_subdivision", key, *distinct)
        result.conditions.add("subdivided_survey_number")
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.PROPERTY_IDENTITY.value,
            severity=Severity.MEDIUM.value,
            title="{} is written differently across documents ({})".format(label, ", ".join(distinct)),
            description=(
                "The documents refer to {vals}. These share the same parent survey number, so a "
                "subdivision (phodi), renumbering or partial description may explain the difference. "
                "The records needed to confirm that have not been supplied."
            ).format(vals=" and ".join(distinct)),
            consequence="If the variants are not the same parcel, part of the property being transacted may not be covered by the title documents.",
            recommended_action="Obtain the phodi / subdivision record and the survey sketch showing how the parent survey number was divided.",
            required_documents=["Phodi / subdivision (hissa) record", "Survey sketch / Tippani"],
            confidence=0.75, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.CONFLICTING.value,
            evidence=[Evidence.from_value(vs[0], "Recorded as {} in {}.".format(group, vs[0].document_name))
                      for group, vs in sorted(groups.items())][:6],
            detector="identity_subdivision",
        ))
        return

    fp = ProposedFinding.make_fingerprint("identity_conflict", key, *distinct)
    result.findings.append(ProposedFinding(
        fingerprint=fp,
        category=FindingCategory.PROPERTY_IDENTITY.value,
        severity=severity,
        title="Conflicting {} across documents: {}".format(label.lower(), ", ".join(distinct[:4])),
        description=(
            "The documents in this file describe the property with different {label} values: {detail}. "
            "Nothing on record explains the difference."
        ).format(label=label.lower(), detail="; ".join(
            "{} in {}".format(group, ", ".join(sorted({v.document_name for v in vs})[:3]))
            for group, vs in sorted(groups.items())
        )),
        consequence="The documents may relate to different properties, or one of them may describe the property incorrectly.",
        recommended_action="Obtain a rectification deed, the official record reconciling the identifiers, or confirmation from the issuing authority.",
        required_documents=["Official record reconciling the {}".format(label.lower())],
        confidence=0.8, confirmed=True, requires_legal_review=True,
        verification_status=VerificationStatus.CONFLICTING.value,
        evidence=[Evidence.from_value(vs[0], "Recorded as {} in {}.".format(group, vs[0].document_name))
                  for group, vs in sorted(groups.items())][:6],
        detector="identity_conflict",
    ))
    result.conditions.add("identity_discrepancy")


def _compare_area(ctx: CaseContext, result: AnalysisResult) -> None:
    measurements: List[Tuple[FieldValue, float]] = []
    for v in ctx.values("property_area"):
        sqm = None
        if v.number is not None and v.unit:
            sqm = nz.area_to_sqm(v.number, v.unit)
        else:
            parsed = nz.parse_area(v.display)
            if parsed:
                sqm = parsed[2]
        if sqm:
            measurements.append((v, sqm))

    result.comparisons.append({
        "field": "property_area", "label": "Extent / area",
        "values": [
            {"value": "{} ({:g} sq m)".format(nz.format_area(v.number, v.unit) if v.number else v.display, sqm),
             "documents": [v.document_name], "pages": [v.page_no] if v.page_no else []}
            for v, sqm in measurements
        ],
        "consistent": len({round(s, 1) for _v, s in measurements}) <= 1,
    })
    if len(measurements) < 2:
        return

    # Compare the largest stated extent in each document - deeds often restate
    # the same parcel in more than one unit.
    per_doc: Dict[str, Tuple[FieldValue, float]] = {}
    for v, sqm in measurements:
        current = per_doc.get(v.document_id)
        if current is None or sqm > current[1]:
            per_doc[v.document_id] = (v, sqm)
    if len(per_doc) < 2:
        return

    items = sorted(per_doc.values(), key=lambda t: t[1])
    smallest, largest = items[0], items[-1]
    # Every document stating the smallest and the largest extent is cited, so the
    # reader can see both sides of the discrepancy rather than one example of each.
    small_group = [v for v, sqm in items if abs(sqm - smallest[1]) < 0.5]
    large_group = [v for v, sqm in items if abs(sqm - largest[1]) < 0.5]
    diff = nz.area_difference_pct(smallest[1], largest[1])
    if diff is None or diff <= AREA_TOLERANCE_PCT:
        return

    kharab = ctx.values("kharab_area")
    severity = Severity.HIGH.value if diff > AREA_MATERIAL_PCT else Severity.MEDIUM.value
    explanation = ""
    if kharab:
        explanation = (" One document records a kharab (uncultivable) area of {}; kharab is sometimes "
                       "included in and sometimes excluded from the stated extent, which can account for "
                       "part of the difference.").format(kharab[0].display)
        severity = Severity.MEDIUM.value

    fp = ProposedFinding.make_fingerprint("area_mismatch", round(smallest[1], 1), round(largest[1], 1))
    result.findings.append(ProposedFinding(
        fingerprint=fp,
        category=FindingCategory.PROPERTY_IDENTITY.value,
        severity=severity,
        title="Stated extent differs by {:.1f}% between documents".format(diff),
        description=(
            "{doc_small} states an extent of {small} ({small_sqm:g} sq m) while {doc_large} states "
            "{large} ({large_sqm:g} sq m) - a difference of {diff:.1f}% ({delta:g} sq m).{expl}"
        ).format(
            doc_small=", ".join(sorted({v.document_name for v in small_group})),
            small=smallest[0].display, small_sqm=smallest[1],
            doc_large=", ".join(sorted({v.document_name for v in large_group})),
            large=largest[0].display, large_sqm=largest[1],
            diff=diff, delta=round(largest[1] - smallest[1], 2), expl=explanation,
        ),
        consequence="The buyer may receive less land than the title document describes, or part of the parcel may lie outside the documented extent.",
        recommended_action="Obtain the survey sketch and a measurement on site by a licensed surveyor, and reconcile the extent against the revenue record.",
        required_documents=["Survey sketch / Tippani", "Surveyor's measurement report", "Current RTC / khata extract"],
        confidence=0.8, confirmed=True, requires_legal_review=False,
        verification_status=VerificationStatus.CONFLICTING.value,
        evidence=[Evidence.from_value(v, "States {} in {}.".format(v.display, v.document_name))
                  for v in (small_group + large_group)[:6]],
        detector="area_mismatch",
    ))
    result.conditions.add("area_discrepancy")


def _compare_boundaries(ctx: CaseContext, result: AnalysisResult) -> None:
    for direction in ("north", "south", "east", "west"):
        key = "boundary_{}".format(direction)
        values = ctx.values(key)
        if len(values) < 2:
            continue
        per_doc: Dict[str, FieldValue] = {}
        for v in values:
            per_doc.setdefault(v.document_id, v)
        if len(per_doc) < 2:
            continue
        texts = [(d, v) for d, v in per_doc.items()]
        mismatched = []
        base = texts[0][1]
        for _doc_id, other in texts[1:]:
            if _script_of(base.display) != _script_of(other.display):
                # "SITE NO 90" and "ಸೈಟ್ ನಂ90" score near zero against each other
                # however identical they are, because the letters differ entirely.
                # Without transliteration there is no basis for calling this a
                # discrepancy, so it is not reported as one.
                continue
            if nz.name_similarity(base.display, other.display) < 60:
                mismatched.append(other)
        if not mismatched:
            continue
        fp = ProposedFinding.make_fingerprint("boundary_mismatch", direction,
                                              base.display.lower(), mismatched[0].display.lower())
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.PROPERTY_IDENTITY.value,
            severity=Severity.MEDIUM.value,
            title="Boundary on the {} is described differently across documents".format(direction),
            description=(
                "{doc_a} describes the {dir} boundary as \"{a}\" while {doc_b} describes it as \"{b}\". "
                "Boundary descriptions do change as neighbouring holdings are transferred, so this is "
                "not necessarily a defect - but it has not been reconciled."
            ).format(doc_a=base.document_name, doc_b=mismatched[0].document_name, dir=direction,
                     a=base.display[:80], b=mismatched[0].display[:80]),
            consequence="If the parcels are not the same, the documents may not describe the property being transacted.",
            recommended_action="Compare the boundaries against the survey sketch and confirm them on site.",
            required_documents=["Survey sketch / Tippani", "Site inspection report"],
            confidence=0.55, confirmed=False, requires_legal_review=False,
            verification_status=VerificationStatus.CONFLICTING.value,
            evidence=[Evidence.from_value(base), Evidence.from_value(mismatched[0])],
            detector="boundary_mismatch",
        ))


def _compare_with_case_record(ctx: CaseContext, result: AnalysisResult) -> None:
    """Compare what the user entered on the case against what the documents say."""
    checks = [
        (ctx.case.survey_number, "survey_number", "Survey number", nz.normalize_survey_number),
        (ctx.case.khata_number, "khata_number", "Khata number", nz.normalize_identifier),
        (ctx.case.village, "village", "Village", lambda v: nz.normalize_name(v).lower()),
    ]
    for declared, key, label, normaliser in checks:
        if not declared:
            continue
        values = ctx.values(key)
        if not values:
            continue
        declared_norm = normaliser(declared)
        found = {normaliser(v.display) for v in values if v.display}
        if declared_norm in found or not found:
            continue
        fp = ProposedFinding.make_fingerprint("case_record_mismatch", key, declared_norm)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.PROPERTY_IDENTITY.value,
            severity=Severity.MEDIUM.value,
            title="{} recorded on the case does not appear in any document".format(label),
            description=(
                "The case records the {label} as \"{declared}\", but the documents refer to {found}."
            ).format(label=label.lower(), declared=declared, found=", ".join(sorted(found)[:4])),
            consequence="Either the case details are wrong, or the documents supplied relate to a different property.",
            recommended_action="Confirm the correct identifier and either correct the case record or obtain the documents for the right property.",
            required_documents=[],
            confidence=0.7, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.CONFLICTING.value,
            evidence=[Evidence.from_value(values[0])],
            detector="case_record_mismatch",
        ))


# ---------------------------------------------------------------------------
# C. Encumbrance and liability
# ---------------------------------------------------------------------------
def _verify_encumbrance(ctx: CaseContext, result: AnalysisResult) -> None:
    mortgage_docs = ctx.by_type(*MORTGAGE_TYPES)
    mortgage_mentions = ctx.tagged("mortgage_status", "mortgage_indicated") + \
        ctx.tagged("mortgage_status", "loan_indicated")
    release_docs = ctx.by_type(*MORTGAGE_RELEASE_TYPES)
    release_mentions = ctx.tagged("mortgage_status", "release_indicated")

    if (mortgage_docs or mortgage_mentions) and not (release_docs or release_mentions):
        sources = [d.filename for d in mortgage_docs] or sorted({v.document_name for v in mortgage_mentions})
        lender = next((v.display for v in ctx.values("mortgage_lender")), None)
        amount = next((v.display for v in ctx.values("loan_amount")), None)
        fp = ProposedFinding.make_fingerprint("mortgage_unreleased", *sorted(sources))
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.ENCUMBRANCE.value,
            severity=Severity.CRITICAL.value if mortgage_docs else Severity.HIGH.value,
            title="A mortgage or charge is indicated and no release document is on record",
            description=(
                "{source} indicate{s} that the property was mortgaged or charged{lender}{amount}. "
                "No loan closure certificate, no-dues certificate, release deed or reconveyance has been "
                "supplied, so the charge cannot be shown to have been discharged."
            ).format(source=", ".join(sources[:4]), s="" if len(sources) > 1 else "s",
                     lender=" to {}".format(lender) if lender else "",
                     amount=" for {}".format(amount) if amount else ""),
            consequence=("A subsisting mortgage travels with the property. The lender's claim would rank "
                         "ahead of the buyer's, and the transfer may require the lender's consent."),
            recommended_action=("Obtain the loan closure / no-dues certificate and the registered release "
                                "of mortgage from the lender, and confirm the discharge appears in a "
                                "current Encumbrance Certificate."),
            required_documents=["Loan closure / no-dues certificate", "Registered release of mortgage or reconveyance deed",
                                "Current Encumbrance Certificate showing the discharge"],
            confidence=0.85 if mortgage_docs else 0.65,
            confirmed=bool(mortgage_docs), requires_legal_review=True,
            verification_status=VerificationStatus.DOCUMENTED.value if mortgage_docs else VerificationStatus.UNVERIFIED.value,
            evidence=([Evidence.from_doc(d, "Mortgage document on record.") for d in mortgage_docs[:3]] or
                      [Evidence.from_value(v, "Mortgage reference in {}.".format(v.document_name))
                       for v in mortgage_mentions[:3]]),
            detector="mortgage_unreleased",
        ))
        result.conditions.add("mortgage_unresolved")
    elif mortgage_docs and (release_docs or release_mentions):
        result.notes.append(
            "A mortgage is documented and a release or closure document is also on record; the discharge "
            "should still be confirmed against a current Encumbrance Certificate."
        )
        result.conditions.add("mortgage_released_claimed")

    _verify_ec_coverage(ctx, result)
    _verify_ec_consistency(ctx, result, bool(mortgage_docs or mortgage_mentions))

    for v in ctx.tagged("litigation_mention", "attachment"):
        fp = ProposedFinding.make_fingerprint("attachment_reference", v.document_id, (v.evidence or "")[:60])
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.ENCUMBRANCE.value,
            severity=Severity.HIGH.value,
            title="A reference to an attachment or prohibitory order appears in the documents",
            description=("{doc} contains language referring to an attachment or prohibitory order over the "
                         "property. The document on record does not establish whether the order is still "
                         "in force.").format(doc=v.document_name),
            consequence="An attachment restrains transfer until it is lifted.",
            recommended_action="Obtain the order itself and confirm its current status with the issuing court or authority.",
            required_documents=["Copy of the attachment / prohibitory order", "Current status certificate from the issuing authority"],
            confidence=0.6, confirmed=False, requires_legal_review=True,
            verification_status=VerificationStatus.UNVERIFIED.value,
            evidence=[Evidence.from_value(v)],
            detector="attachment_reference",
        ))


def _verify_ec_coverage(ctx: CaseContext, result: AnalysisResult) -> None:
    ec_docs = ctx.by_type("encumbrance_certificate")
    if not ec_docs:
        result.conditions.add("ec_absent")
        return

    spans: List[Tuple[date, date, DocFacts, FieldValue]] = []
    for doc in ec_docs:
        f, t = doc.first("ec_period_from"), doc.first("ec_period_to")
        df = nz.parse_date(f.display) if f else None
        dt_ = nz.parse_date(t.display) if t else None
        if df and dt_ and dt_ >= df:
            spans.append((df, dt_, doc, f))
        else:
            fp = ProposedFinding.make_fingerprint("ec_period_unclear", doc.id)
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.ENCUMBRANCE.value,
                severity=Severity.MEDIUM.value,
                title="The period certified by {} could not be determined".format(doc.filename),
                description=("The Encumbrance Certificate does not state a legible period, or the period "
                             "could not be read from the supplied copy. Without the certified period the "
                             "certificate's coverage cannot be assessed."),
                consequence="The certificate cannot be relied on to show the absence of registered charges for any particular period.",
                recommended_action="Obtain a clear copy of the certificate showing the certified period.",
                required_documents=["Legible Encumbrance Certificate stating the certified period"],
                confidence=0.7, confirmed=True, requires_legal_review=False,
                verification_status=VerificationStatus.UNVERIFIED.value,
                evidence=[Evidence.from_doc(doc)],
                detector="ec_period_unclear",
            ))
    if not spans:
        result.conditions.add("ec_period_unknown")
        return

    spans.sort(key=lambda s: s[0])
    merged: List[List[Any]] = []
    for start, end, doc, fv in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
            merged[-1][2].append(doc)
        else:
            merged.append([start, end, [doc]])

    required_start = date(nz.today().year - ctx.ec_lookback_years, nz.today().month, 1)
    covered_start = merged[0][0]
    covered_end = merged[-1][1]
    gaps: List[Tuple[date, date]] = []
    for i in range(1, len(merged)):
        if merged[i][0] > merged[i - 1][1]:
            gaps.append((merged[i - 1][1], merged[i][0]))

    result.comparisons.append({
        "field": "ec_coverage", "label": "Encumbrance Certificate coverage",
        "values": [{"value": "{} to {}".format(nz.format_date(s.isoformat()), nz.format_date(e.isoformat())),
                    "documents": [d.filename for d in docs], "pages": []} for s, e, docs in merged],
        "consistent": not gaps and covered_start <= required_start,
    })

    years_covered = (covered_end - covered_start).days / 365.25
    if covered_start > required_start:
        fp = ProposedFinding.make_fingerprint("ec_short_period", covered_start.isoformat())
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.ENCUMBRANCE.value,
            severity=Severity.HIGH.value if years_covered < ctx.ec_lookback_years / 2 else Severity.MEDIUM.value,
            title="Encumbrance Certificate covers about {:.0f} years, not the {}-year review period".format(
                years_covered, ctx.ec_lookback_years),
            description=(
                "The certificate(s) on record cover {start} to {end}. Registered transactions before "
                "{start} have not been certified. A certificate for a shorter period says nothing about "
                "what is registered outside it."
            ).format(start=nz.format_date(covered_start.isoformat()), end=nz.format_date(covered_end.isoformat())),
            consequence="A mortgage, attachment or competing transfer registered before the certified period would not appear.",
            recommended_action="Apply for an Encumbrance Certificate covering {} to {}.".format(
                nz.format_date(required_start.isoformat()), nz.format_date(covered_start.isoformat())),
            required_documents=["Encumbrance Certificate for {} to {}".format(
                required_start.year, covered_start.year)],
            confidence=0.9, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.DOCUMENTED.value,
            evidence=[Evidence.from_doc(d, "Certified period starts {}.".format(
                nz.format_date(covered_start.isoformat()))) for d in merged[0][2][:2]],
            detector="ec_short_period",
        ))
        result.conditions.add("ec_incomplete")

    for gap_start, gap_end in gaps:
        fp = ProposedFinding.make_fingerprint("ec_gap", gap_start.isoformat(), gap_end.isoformat())
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.ENCUMBRANCE.value,
            severity=Severity.HIGH.value,
            title="Gap in Encumbrance Certificate coverage between {} and {}".format(
                nz.format_date(gap_start.isoformat()), nz.format_date(gap_end.isoformat())),
            description=("The certificates on record do not cover the period from {} to {}. Nothing is "
                         "certified about registrations in that window.").format(
                nz.format_date(gap_start.isoformat()), nz.format_date(gap_end.isoformat())),
            consequence="Charges created in the uncovered window would not be visible.",
            recommended_action="Apply for an Encumbrance Certificate covering the uncovered period.",
            required_documents=["Encumbrance Certificate for {} to {}".format(gap_start.year, gap_end.year)],
            confidence=0.9, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.DOCUMENTED.value,
            evidence=[Evidence.from_doc(merged[0][2][0])],
            detector="ec_gap",
        ))
        result.conditions.add("ec_incomplete")

    stale_days = (nz.today() - covered_end).days
    if stale_days > 180:
        fp = ProposedFinding.make_fingerprint("ec_stale", covered_end.isoformat())
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.ENCUMBRANCE.value,
            severity=Severity.MEDIUM.value,
            title="The latest Encumbrance Certificate ends {} and is not current".format(
                nz.format_date(covered_end.isoformat())),
            description=("The most recent certificate runs only to {}, about {} months ago. Registrations "
                         "since then are not covered.").format(
                nz.format_date(covered_end.isoformat()), int(stale_days / 30)),
            consequence="A charge or transfer registered after the certified date would not appear.",
            recommended_action="Obtain a fresh Encumbrance Certificate up to the current date, and again immediately before completion.",
            required_documents=["Current Encumbrance Certificate up to today's date"],
            confidence=0.9, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.DOCUMENTED.value,
            evidence=[Evidence.from_doc(merged[-1][2][-1])],
            detector="ec_stale",
        ))
        result.conditions.add("ec_stale")


def _verify_ec_consistency(ctx: CaseContext, result: AnalysisResult, mortgage_present: bool) -> None:
    """An EC that reports nothing, while other documents report a charge, is a conflict."""
    ec_docs = ctx.by_type("encumbrance_certificate")
    if not ec_docs:
        return
    nil_declared = [d for d in ec_docs if d.has_tag("ec_nil", "true")]
    if nil_declared and mortgage_present:
        fp = ProposedFinding.make_fingerprint("ec_conflicts_mortgage", nil_declared[0].id)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.ENCUMBRANCE.value,
            severity=Severity.HIGH.value,
            title="Encumbrance Certificate reports no entries while other documents indicate a charge",
            description=(
                "{ec} states that no encumbrance entries were found, but other documents in this file "
                "refer to a mortgage or charge. Either the charge falls outside the certified period, it "
                "was created by deposit of title deeds and never registered, or the certificate relates "
                "to a different property."
            ).format(ec=nil_declared[0].filename),
            consequence=("An equitable mortgage created by deposit of title deeds does not always appear "
                         "in an Encumbrance Certificate, so a nil certificate does not prove the property "
                         "is unencumbered."),
            recommended_action=("Reconcile the certified period against the date of the charge, and obtain "
                                "written confirmation from the lender about the current status of the loan."),
            required_documents=["Lender's confirmation of the loan status", "Encumbrance Certificate covering the date of the charge"],
            confidence=0.8, confirmed=True, requires_legal_review=True,
            verification_status=VerificationStatus.CONFLICTING.value,
            evidence=[Evidence.from_doc(nil_declared[0], "Certificate reports no entries.")],
            detector="ec_conflicts_mortgage",
        ))

    # Registered deeds that ought to appear in an EC covering their date.
    for doc in ctx.by_type(*TITLE_TRANSFER_TYPES):
        reg_date = nz.parse_date(doc.value("registration_date") or "")
        if not reg_date:
            continue
        for ec in ec_docs:
            f, t = ec.first("ec_period_from"), ec.first("ec_period_to")
            df = nz.parse_date(f.display) if f else None
            dt_ = nz.parse_date(t.display) if t else None
            if not (df and dt_ and df <= reg_date <= dt_):
                continue
            if not ec.has_tag("ec_nil", "true"):
                continue
            fp = ProposedFinding.make_fingerprint("ec_missing_registered_deed", ec.id, doc.id)
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.ENCUMBRANCE.value,
                severity=Severity.HIGH.value,
                title="A registered deed does not appear in the Encumbrance Certificate covering its date",
                description=(
                    "{deed} is recorded as registered on {when}, which falls inside the period certified "
                    "by {ec}, yet that certificate reports no entries. The deed, the certificate, or the "
                    "property identifiers used to obtain the certificate may not match."
                ).format(deed=doc.filename, when=nz.format_date(reg_date.isoformat()), ec=ec.filename),
                consequence="Either the certificate was issued for different property identifiers, or the registration cannot be confirmed.",
                recommended_action="Re-apply for the certificate using the exact survey/khata identifiers in the deed, and verify the registration entry at the Sub-Registrar's office.",
                required_documents=["Encumbrance Certificate obtained against the exact property identifiers",
                                    "Certified copy of the registration entry"],
                confidence=0.7, confirmed=True, requires_legal_review=True,
                verification_status=VerificationStatus.CONFLICTING.value,
                evidence=[Evidence.from_doc(doc, "Registered on {}.".format(nz.format_date(reg_date.isoformat()))),
                          Evidence.from_doc(ec, "Certificate reports no entries for the period.")],
                detector="ec_missing_registered_deed",
            ))


# ---------------------------------------------------------------------------
# D. Land use and approvals
# ---------------------------------------------------------------------------
def _verify_land_use(ctx: CaseContext, result: AnalysisResult) -> None:
    prop_type = ctx.case.property_type
    non_agricultural_use = prop_type not in ("agricultural_land",)

    if "agricultural_origin" in result.conditions and non_agricultural_use:
        if not ctx.has_type("land_conversion_order"):
            fp = ProposedFinding.make_fingerprint("conversion_missing", prop_type)
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.LAND_USE.value,
                severity=Severity.CRITICAL.value if prop_type in ("apartment", "under_construction", "commercial", "industrial")
                else Severity.HIGH.value,
                title="No land conversion order on record for a property intended for non-agricultural use",
                description=(
                    "The records indicate the land is, or originated as, agricultural land, and the case "
                    "describes it as {ptype}. No conversion order permitting non-agricultural use has been "
                    "supplied."
                ).format(ptype=prop_type.replace("_", " ")),
                consequence=("Use or development of unconverted agricultural land for a non-agricultural "
                             "purpose can be unlawful; the local body may refuse khata, plan sanction and "
                             "building approval, and lenders commonly refuse to fund such property."),
                recommended_action="Obtain the conversion order from the office of the Deputy Commissioner and confirm it covers the full extent and the intended purpose.",
                required_documents=["Land conversion order (DC conversion)"],
                confidence=0.8, confirmed=True, requires_legal_review=True,
                verification_status=VerificationStatus.DOCUMENTED.value,
                evidence=[Evidence.from_doc(d, "Indicates agricultural land records.")
                          for d in ctx.by_type(*AGRICULTURAL_INDICATOR_TYPES)[:2]],
                detector="conversion_missing",
            ))
            result.conditions.add("conversion_missing")
        else:
            _check_conversion_extent(ctx, result)

    if "built_property" in result.conditions and not ctx.has_type(
        "approved_building_plan", "building_permit", "commencement_certificate"
    ):
        fp = ProposedFinding.make_fingerprint("building_approval_missing", prop_type)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.LAND_USE.value,
            severity=Severity.HIGH.value,
            title="No sanctioned building plan or building licence on record",
            description=("The case describes a {ptype}, but no sanctioned plan, building licence or "
                         "commencement certificate has been supplied, so it cannot be established that "
                         "the construction was authorised.").format(ptype=prop_type.replace("_", " ")),
            consequence="Unauthorised or deviated construction can attract penalties, demolition, or refusal of regularisation, and affects resale and financing.",
            recommended_action="Obtain the sanctioned plan and licence from the planning authority and compare them with what exists on site.",
            required_documents=["Sanctioned building plan", "Building licence / permit"],
            confidence=0.75, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.NOT_PERFORMED.value,
            evidence=[],
            detector="building_approval_missing",
        ))

    if "completed_construction" in result.conditions and not ctx.has_type(
        "occupancy_certificate", "completion_certificate"
    ):
        fp = ProposedFinding.make_fingerprint("oc_missing", prop_type)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.LAND_USE.value,
            severity=Severity.MEDIUM.value,
            title="No Occupancy or Completion Certificate on record",
            description=("The property appears to be a completed building, but no Occupancy Certificate or "
                         "Completion Certificate has been supplied."),
            consequence="Occupation without an OC can attract penalties and complicates resale, loans and utility connections.",
            recommended_action="Obtain the Occupancy Certificate for the building or block from the planning authority.",
            required_documents=["Occupancy Certificate", "Completion Certificate"],
            confidence=0.7, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.NOT_PERFORMED.value,
            evidence=[],
            detector="oc_missing",
        ))

    for v in ctx.values("validity_date"):
        expiry = nz.parse_date(v.display)
        if expiry and expiry < nz.today():
            fp = ProposedFinding.make_fingerprint("approval_expired", v.document_id, expiry.isoformat())
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.LAND_USE.value,
                severity=Severity.MEDIUM.value,
                title="An approval on record expired on {}".format(nz.format_date(expiry.isoformat())),
                description="{doc} states a validity ending {when}, which has passed.".format(
                    doc=v.document_name, when=nz.format_date(expiry.isoformat())),
                consequence="An expired sanction or permit may need renewal before the work or use can lawfully continue.",
                recommended_action="Obtain the renewed approval or written confirmation from the issuing authority that it remains effective.",
                required_documents=["Renewed or extended approval"],
                confidence=0.75, confirmed=True, requires_legal_review=False,
                verification_status=VerificationStatus.DOCUMENTED.value,
                evidence=[Evidence.from_value(v)],
                detector="approval_expired",
            ))


def _check_conversion_extent(ctx: CaseContext, result: AnalysisResult) -> None:
    """A conversion order that covers less than the parcel leaves part unconverted."""
    orders = ctx.by_type("land_conversion_order")
    deed_areas = [
        nz.area_to_sqm(v.number, v.unit) for v in ctx.values("property_area")
        if v.number and v.unit and v.document_type in TITLE_TRANSFER_TYPES
    ]
    deed_areas = [a for a in deed_areas if a]
    if not deed_areas:
        return
    deed_max = max(deed_areas)
    for order in orders:
        order_area = order.first("property_area")
        if not order_area or not order_area.number or not order_area.unit:
            continue
        order_sqm = nz.area_to_sqm(order_area.number, order_area.unit)
        if not order_sqm:
            continue
        if order_sqm < deed_max * 0.97:
            fp = ProposedFinding.make_fingerprint("conversion_partial", order.id, round(order_sqm, 1))
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.LAND_USE.value,
                severity=Severity.HIGH.value,
                title="Conversion order covers a smaller extent than the property described in the deed",
                description=(
                    "{order} converts {ordered:g} sq m while the title documents describe {deed:g} sq m. "
                    "About {delta:g} sq m appears to remain unconverted."
                ).format(order=order.filename, ordered=order_sqm, deed=deed_max,
                         delta=round(deed_max - order_sqm, 1)),
                consequence="The unconverted portion cannot lawfully be used or developed for a non-agricultural purpose.",
                recommended_action="Obtain a conversion order covering the balance extent, or confirm which portion is covered.",
                required_documents=["Conversion order covering the full extent"],
                confidence=0.8, confirmed=True, requires_legal_review=True,
                verification_status=VerificationStatus.CONFLICTING.value,
                evidence=[Evidence.from_value(order_area, "Extent converted under the order.")],
                detector="conversion_partial",
            ))


# ---------------------------------------------------------------------------
# E. Legal and litigation
# ---------------------------------------------------------------------------
_LITIGATION_SEVERITY = {
    "injunction": (Severity.CRITICAL.value, "An injunction or stay order restrains dealings with the property."),
    "pending_litigation": (Severity.HIGH.value, "A pending suit can prevent or unwind a transfer."),
    "acquisition": (Severity.CRITICAL.value, "Land under acquisition proceedings may be taken by the State; compensation replaces the property."),
    "dispute_reference": (Severity.MEDIUM.value, "A disclosed dispute may ripen into litigation affecting the property."),
    "court_decision": (Severity.INFORMATIONAL.value, "A court decision affecting the property must be read in full to understand its effect."),
}


def _verify_legal(ctx: CaseContext, result: AnalysisResult) -> None:
    by_tag: Dict[str, List[FieldValue]] = defaultdict(list)
    for v in ctx.values("litigation_mention"):
        by_tag[(v.norm or v.raw)].append(v)

    for tag, values in by_tag.items():
        if tag == "attachment":
            continue  # handled under encumbrance
        severity, consequence = _LITIGATION_SEVERITY.get(
            tag, (Severity.MEDIUM.value, "The reference needs to be read in context."))
        case_refs = sorted({v.display for v in ctx.values("court_case_number")})
        sources = sorted({v.document_name for v in values})
        fp = ProposedFinding.make_fingerprint("litigation_reference", tag, *sources)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.LEGAL.value,
            severity=severity,
            title="Reference to {} in the supplied documents".format(tag.replace("_", " ")),
            description=(
                "{sources} contain{s} language referring to {tag}{refs}. The supplied documents show that "
                "the subject was raised; they do not establish whether any proceeding is currently pending, "
                "has been decided, or has been withdrawn."
            ).format(sources=", ".join(sources[:3]), s="" if len(sources) > 1 else "s",
                     tag=tag.replace("_", " "),
                     refs=" (case reference(s): {})".format(", ".join(case_refs[:4])) if case_refs else ""),
            consequence=consequence,
            recommended_action=("Obtain the complete court or authority record for the reference and a "
                                "current status report, and have an advocate run an independent search."),
            required_documents=["Complete copy of the order / proceedings", "Current case status report"],
            confidence=0.6, confirmed=False, requires_legal_review=True,
            verification_status=VerificationStatus.UNVERIFIED.value,
            evidence=[Evidence.from_value(v, "Reference found in {}.".format(v.document_name)) for v in values[:4]],
            detector="litigation_reference",
        ))
        result.conditions.add("litigation_reference")

    for v in ctx.tagged("restriction_mention", "transfer_restriction"):
        fp = ProposedFinding.make_fingerprint("transfer_restriction", v.document_id, (v.evidence or "")[:60])
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.LEGAL.value,
            severity=Severity.HIGH.value,
            title="A restriction on transfer is referred to in the documents",
            description=("{doc} contains language indicating that the property may not be transferred "
                         "freely, or that prior permission is required.").format(doc=v.document_name),
            consequence="A transfer made in breach of a statutory or contractual restriction can be set aside.",
            recommended_action="Identify the source of the restriction and obtain either the required permission or confirmation that the restriction has lapsed.",
            required_documents=["Document creating the restriction", "Permission or no-objection from the competent authority"],
            confidence=0.65, confirmed=False, requires_legal_review=True,
            verification_status=VerificationStatus.UNVERIFIED.value,
            evidence=[Evidence.from_value(v)],
            detector="transfer_restriction",
        ))

    if "grant_land_indicator" in result.conditions:
        values = ctx.tagged("restriction_mention", "grant_land_indicator")
        fp = ProposedFinding.make_fingerprint("grant_land", *sorted({v.document_id for v in values}))
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.LEGAL.value,
            severity=Severity.HIGH.value,
            title="The records contain language suggesting the land may be granted land",
            description=("{docs} refer to a grant, darkhast, inam or similar origin. Land granted to "
                         "members of Scheduled Castes or Scheduled Tribes can carry a statutory bar on "
                         "alienation under the PTCL Act, and transfers in breach can be set aside even "
                         "decades later.").format(docs=", ".join(sorted({v.document_name for v in values})[:3])),
            consequence="A transfer of restricted granted land can be annulled and the land restored to the original grantee or their heirs.",
            recommended_action="Examine the original grant order and the RTC remarks column, and obtain confirmation from the Assistant Commissioner that no PTCL proceedings affect the land.",
            required_documents=["Original grant / darkhast order", "Confirmation that no PTCL proceedings are pending"],
            confidence=0.55, confirmed=False, requires_legal_review=True,
            verification_status=VerificationStatus.UNVERIFIED.value,
            evidence=[Evidence.from_value(v) for v in values[:3]],
            detector="grant_land",
        ))

    if "poa_used" in result.conditions:
        poas = ctx.by_type("power_of_attorney")
        fp = ProposedFinding.make_fingerprint("poa_present", *sorted(d.id for d in poas))
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.LEGAL.value,
            severity=Severity.MEDIUM.value,
            title="A power of attorney is part of the transaction documents",
            description=("{docs} is a power of attorney. Where a transfer is executed by an attorney "
                         "holder, the instrument's scope, its registration, and whether it remained in "
                         "force on the date of execution all need to be confirmed - a power of attorney "
                         "is revoked by the principal's death.").format(
                docs=", ".join(d.filename for d in poas[:3])),
            consequence="A transfer executed under a revoked, unregistered or insufficient power of attorney may be invalid.",
            recommended_action="Confirm the power of attorney is registered, covers the sale of this property, and was in force on the date of execution; obtain the principal's confirmation where possible.",
            required_documents=["Registered power of attorney", "Confirmation that the power of attorney subsists"],
            confidence=0.7, confirmed=True, requires_legal_review=True,
            verification_status=VerificationStatus.DOCUMENTED.value,
            evidence=[Evidence.from_doc(d) for d in poas[:3]],
            detector="poa_present",
        ))


# ---------------------------------------------------------------------------
# F. Document integrity and consistency
# ---------------------------------------------------------------------------
_INTEGRITY_SEVERITY = {
    "missing_pages": Severity.HIGH.value,
    "unreadable": Severity.MEDIUM.value,
    "missing_annexure": Severity.MEDIUM.value,
    "unreadable_pages": Severity.MEDIUM.value,
    "ocr_uncertainty": Severity.MEDIUM.value,
    "prompt_injection": Severity.HIGH.value,
    "extraction_note": Severity.INFORMATIONAL.value,
}


def _verify_document_integrity(ctx: CaseContext, result: AnalysisResult) -> None:
    for doc in ctx.docs:
        for issue in doc.issues:
            itype = issue.get("type", "extraction_note")
            severity = _INTEGRITY_SEVERITY.get(itype, Severity.LOW.value)
            fp = ProposedFinding.make_fingerprint("integrity", doc.id, itype, (issue.get("detail") or "")[:60])
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.DOCUMENT_INTEGRITY.value,
                severity=severity,
                title="{}: {}".format(doc.filename, _integrity_title(itype)),
                description="{} {}".format(issue.get("detail", ""), _integrity_caveat(itype)).strip(),
                consequence=_integrity_consequence(itype),
                recommended_action=_integrity_action(itype),
                required_documents=["Complete, legible copy of {}".format(doc.filename)]
                if itype in ("missing_pages", "unreadable_pages", "ocr_uncertainty") else [],
                confidence=0.75, confirmed=itype in ("missing_pages", "unreadable_pages"),
                requires_legal_review=itype == "prompt_injection",
                verification_status=VerificationStatus.DOCUMENTED.value,
                evidence=[Evidence.from_doc(doc, issue.get("detail"))],
                detector="integrity",
            ))

    _detect_duplicate_registrations(ctx, result)
    _detect_date_inconsistencies(ctx, result)


def _integrity_title(itype: str) -> str:
    return {
        "missing_pages": "pages appear to be missing",
        "missing_annexure": "a referenced annexure is not present",
        "unreadable_pages": "pages could not be read",
        "ocr_uncertainty": "text recognition confidence is low",
        "prompt_injection": "the document contains text addressed to an automated system",
        "extraction_note": "note from text extraction",
    }.get(itype, itype.replace("_", " "))


def _integrity_caveat(itype: str) -> str:
    if itype in ("missing_pages", "unreadable_pages", "ocr_uncertainty"):
        return ("Parts of this document were not assessed; nothing has been assumed about their "
                "contents.")
    if itype == "prompt_injection":
        return ("The text was treated as document content only and was not acted on. Text of this kind "
                "does not belong in a property document and the original should be examined.")
    return ""


def _integrity_consequence(itype: str) -> str:
    return {
        "missing_pages": "Terms, schedules or signatures on the missing pages have not been reviewed.",
        "missing_annexure": "The annexure may carry the property schedule or a material condition.",
        "unreadable_pages": "The unread content may contain material terms.",
        "ocr_uncertainty": "Values read from these pages may be wrong.",
        "prompt_injection": "The document may have been tampered with, or assembled from an untrusted source.",
        "extraction_note": "Limits on what could be read from this file.",
    }.get(itype, "The document could not be fully assessed.")


def _integrity_action(itype: str) -> str:
    return {
        "missing_pages": "Obtain the complete document, preferably a certified copy from the registering office.",
        "missing_annexure": "Obtain the referenced annexure or schedule.",
        "unreadable_pages": "Obtain a clearer scan or the original for inspection.",
        "ocr_uncertainty": "Verify the extracted values against the original document.",
        "prompt_injection": "Inspect the original document and establish its provenance before relying on it.",
        "extraction_note": "No action required unless the content matters to a specific question.",
    }.get(itype, "Obtain a complete and legible copy.")


def _detect_duplicate_registrations(ctx: CaseContext, result: AnalysisResult) -> None:
    by_reg: Dict[str, List[DocFacts]] = defaultdict(list)
    for doc in ctx.analysed_docs:
        for v in doc.all("registration_number"):
            key = nz.normalize_identifier(v.display)
            if key and len(key) >= 4:
                by_reg[key].append(doc)
    for reg, docs in by_reg.items():
        unique = {d.id: d for d in docs}
        if len(unique) < 2:
            continue
        types = {d.doc_type for d in unique.values()}
        if len(types) == 1:
            severity, title = Severity.LOW.value, "Two files appear to be copies of the same registered document"
            desc_tail = "They are most likely duplicate copies; only one has been treated as the source."
        else:
            severity, title = Severity.MEDIUM.value, "The same registration number appears on documents of different types"
            desc_tail = "Documents of different types should not share a registration number; one of them may be mislabelled or mis-read."
        fp = ProposedFinding.make_fingerprint("duplicate_registration", reg)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.DOCUMENT_INTEGRITY.value,
            severity=severity,
            title=title,
            description="Registration number {reg} appears in {files}. {tail}".format(
                reg=reg, files=" and ".join(d.filename for d in unique.values()), tail=desc_tail),
            consequence="Duplicate or conflicting copies can cause the same transaction to be counted twice or the wrong version to be relied on.",
            recommended_action="Confirm which file is the operative document and verify the registration entry with the Sub-Registrar.",
            required_documents=[],
            confidence=0.7, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.CONFLICTING.value,
            evidence=[Evidence.from_doc(d) for d in list(unique.values())[:4]],
            detector="duplicate_registration",
        ))


def _detect_date_inconsistencies(ctx: CaseContext, result: AnalysisResult) -> None:
    for doc in ctx.analysed_docs:
        exec_v = doc.first("execution_date")
        reg_v = doc.first("registration_date")
        if not exec_v or not reg_v:
            continue
        d_exec, d_reg = nz.parse_date(exec_v.display), nz.parse_date(reg_v.display)
        if not d_exec or not d_reg:
            continue
        if d_reg < d_exec:
            fp = ProposedFinding.make_fingerprint("date_inconsistency", doc.id, d_exec.isoformat(), d_reg.isoformat())
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.DOCUMENT_INTEGRITY.value,
                severity=Severity.MEDIUM.value,
                title="{}: registration date precedes the execution date".format(doc.filename),
                description=("The document records execution on {ex} and registration on {rg}. A document "
                             "cannot be registered before it is executed, so one of the dates is wrong or "
                             "was misread.").format(ex=nz.format_date(d_exec.isoformat()),
                                                    rg=nz.format_date(d_reg.isoformat())),
                consequence="Date errors undermine the chronology on which the title chain is built.",
                recommended_action="Check both dates against the original document or the certified copy.",
                required_documents=["Certified copy of {}".format(doc.filename)],
                confidence=0.7, confirmed=True, requires_legal_review=False,
                verification_status=VerificationStatus.CONFLICTING.value,
                evidence=[Evidence.from_value(exec_v), Evidence.from_value(reg_v)],
                detector="date_inconsistency",
            ))
        elif (d_reg - d_exec).days > 365 * 2:
            fp = ProposedFinding.make_fingerprint("late_registration", doc.id, d_reg.isoformat())
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.DOCUMENT_INTEGRITY.value,
                severity=Severity.LOW.value,
                title="{}: a long delay between execution and registration".format(doc.filename),
                description=("Executed on {ex} but registered on {rg}, about {yrs:.1f} years later.").format(
                    ex=nz.format_date(d_exec.isoformat()), rg=nz.format_date(d_reg.isoformat()),
                    yrs=(d_reg - d_exec).days / 365.25),
                consequence="A long gap between execution and registration sometimes indicates a dispute or a defect that delayed registration.",
                recommended_action="Ask the seller to explain the delay and check whether anything was registered against the property in the interval.",
                required_documents=[],
                confidence=0.6, confirmed=True, requires_legal_review=False,
                verification_status=VerificationStatus.DOCUMENTED.value,
                evidence=[Evidence.from_value(exec_v), Evidence.from_value(reg_v)],
                detector="late_registration",
            ))

    # A document dated after today is impossible.
    for doc in ctx.analysed_docs:
        when = doc.best_date
        if when and when > nz.today():
            fp = ProposedFinding.make_fingerprint("future_date", doc.id, when.isoformat())
            result.findings.append(ProposedFinding(
                fingerprint=fp,
                category=FindingCategory.DOCUMENT_INTEGRITY.value,
                severity=Severity.MEDIUM.value,
                title="{}: carries a date in the future".format(doc.filename),
                description="The document's date reads {}, which has not yet occurred.".format(
                    nz.format_date(when.isoformat())),
                consequence="The date was either misread or the document is not what it appears to be.",
                recommended_action="Check the date against the original document.",
                required_documents=[],
                confidence=0.7, confirmed=True, requires_legal_review=False,
                verification_status=VerificationStatus.CONFLICTING.value,
                evidence=[Evidence.from_doc(doc)],
                detector="future_date",
            ))


# ---------------------------------------------------------------------------
# G. Process-level findings
# ---------------------------------------------------------------------------
def _verify_process(ctx: CaseContext, result: AnalysisResult) -> None:
    if not ctx.docs:
        result.findings.append(ProposedFinding(
            fingerprint=ProposedFinding.make_fingerprint("no_documents", ctx.case.id),
            category=FindingCategory.PROCESS.value,
            severity=Severity.INFORMATIONAL.value,
            title="No documents have been added to this case yet",
            description="The watched folder for this case is empty, so no assessment has been possible.",
            consequence="Nothing has been assessed.",
            recommended_action="Add the property documents to the case folder; they will be picked up automatically.",
            confidence=1.0, confirmed=True, detector="no_documents",
        ))
        return

    for doc in ctx.failed_docs:
        severity = Severity.MEDIUM.value
        fp = ProposedFinding.make_fingerprint("document_not_processed", doc.id, doc.status)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.PROCESS.value,
            severity=severity,
            title="{} could not be analysed ({})".format(doc.filename, doc.status.replace("_", " ")),
            description=("This file is in the case folder but its contents have not been assessed. "
                         "Nothing in this report accounts for what it may contain."),
            consequence="A material fact in an unprocessed document would be missing from this assessment.",
            recommended_action=("Supply a clearer or converted copy (PDF or DOCX), or review the document "
                                "manually and record the outcome against the case."),
            required_documents=["Readable copy of {}".format(doc.filename)],
            confidence=1.0, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.NOT_PERFORMED.value,
            evidence=[Evidence.from_doc(doc, "Processing status: {}.".format(doc.status))],
            detector="document_not_processed",
        ))

    unknown = [d for d in ctx.analysed_docs if d.doc_type == "unknown"]
    for doc in unknown:
        fp = ProposedFinding.make_fingerprint("unclassified_document", doc.id)
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.PROCESS.value,
            severity=Severity.LOW.value,
            title="{}: document type could not be determined".format(doc.filename),
            description=("The document's text was read but it does not match any known document type with "
                         "sufficient confidence. Its contents have not contributed to the typed checks."),
            consequence="If this is a material document, the checks that depend on its type have not run.",
            recommended_action="Review the document and set its type manually so it is included in the analysis.",
            required_documents=[],
            confidence=1.0, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.NOT_PERFORMED.value,
            evidence=[Evidence.from_doc(doc)],
            detector="unclassified_document",
        ))

    low_conf = [d for d in ctx.analysed_docs if 0 < d.extraction_confidence < 0.5]
    if low_conf:
        fp = ProposedFinding.make_fingerprint("low_extraction_confidence", *sorted(d.id for d in low_conf))
        result.findings.append(ProposedFinding(
            fingerprint=fp,
            category=FindingCategory.PROCESS.value,
            severity=Severity.MEDIUM.value,
            title="Text extraction confidence is low for {} document(s)".format(len(low_conf)),
            description=("Values read from {} may be unreliable. Every field taken from these documents "
                         "should be checked against the original.").format(
                ", ".join(d.filename for d in low_conf[:4])),
            consequence="Comparisons built on mis-read values can produce both false matches and false discrepancies.",
            recommended_action="Supply better-quality scans, or verify the extracted fields against the originals in the document viewer.",
            required_documents=[],
            confidence=1.0, confirmed=True, requires_legal_review=False,
            verification_status=VerificationStatus.UNVERIFIED.value,
            evidence=[Evidence.from_doc(d, "Extraction confidence {:.0%}.".format(d.extraction_confidence))
                      for d in low_conf[:4]],
            detector="low_extraction_confidence",
        ))

    # Scope statement: external records have not been checked.
    result.findings.append(ProposedFinding(
        fingerprint=ProposedFinding.make_fingerprint("scope_no_external_checks", ctx.case.id),
        category=FindingCategory.PROCESS.value,
        severity=Severity.INFORMATIONAL.value,
        title="No external or official record has been checked",
        description=(
            "This assessment is based solely on the documents placed in the case folder. No search has "
            "been made of the Sub-Registrar's records, revenue databases, municipal records, court "
            "registries, RERA registrations or acquisition notifications. A document that exists but was "
            "not supplied cannot be seen, and a supplied copy has not been verified against the official "
            "record."
        ),
        consequence="The absence of a finding in this report is not evidence that the underlying issue does not exist.",
        recommended_action="Commission the external searches listed under pending verification before relying on this assessment.",
        confidence=1.0, confirmed=True, requires_legal_review=True,
        verification_status=VerificationStatus.NOT_PERFORMED.value,
        detector="scope_no_external_checks",
    ))
