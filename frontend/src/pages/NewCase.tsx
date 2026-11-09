import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Callout, Card, ErrorNote } from '../components/ui'
import { useAsync } from '../hooks'
import { useLang } from '../i18n'

const AREA_UNITS = ['acre', 'guntha', 'cent', 'sqft', 'sqm', 'sqyd', 'hectare', 'ankanam', 'ground']

export default function NewCase() {
  const { t, pick } = useLang()
  const reference = useAsync(() => api.reference(), [])
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState<Record<string, string>>({
    property_name: '', property_type: 'residential_plot', transaction_type: 'purchase',
    jurisdiction_code: 'KA', address: '', survey_number: '', subdivision_number: '',
    khata_number: '', plot_number: '', flat_number: '', village: '', taluk: '', district: '',
    state: 'Karnataka', land_area_value: '', land_area_unit: 'acre', dimensions: '',
    claimed_owner: '', seller_name: '', buyer_name: '', purpose: '', assigned_reviewer: '',
    watch_folder: '',
  })

  const set = (key: string) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const body: Record<string, unknown> = {}
    Object.entries(form).forEach(([k, v]) => {
      if (v !== '') body[k] = k === 'land_area_value' ? Number(v) : v
    })
    try {
      const created = await api.createCase(body)
      navigate(`/cases/${created.id}/overview`)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-2xl font-bold">{t('new.title')}</h1>
      <Callout>{t('new.intro')}</Callout>
      {error && <ErrorNote error={error} />}

      <form onSubmit={submit} className="space-y-5">
        <Card title={t('new.property')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className="label">{t('new.propertyName')} *</span>
              <input required className="input mt-1" value={form.property_name}
                     onChange={set('property_name')} placeholder="e.g. Hosahalli agricultural land" />
            </label>
            <label className="block">
              <span className="label">{t('new.propertyType')} *</span>
              <select className="input mt-1" value={form.property_type} onChange={set('property_type')}>
                {(reference.data?.property_types ?? []).map((item) => (
                  <option key={item.value} value={item.value}>{pick(item.label, item.label_kn)}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">{t('new.transactionType')} *</span>
              <select className="input mt-1" value={form.transaction_type} onChange={set('transaction_type')}>
                {(reference.data?.transaction_types ?? []).map((item) => (
                  <option key={item.value} value={item.value}>{pick(item.label, item.label_kn)}</option>
                ))}
              </select>
            </label>
            <label className="block sm:col-span-2">
              <span className="label">{t('field.address')}</span>
              <input className="input mt-1" value={form.address} onChange={set('address')} />
            </label>
          </div>
        </Card>

        <Card title={t('new.identifiers')}>
          <div className="grid gap-4 sm:grid-cols-3">
            {([['survey_number', 'field.surveyNumber'], ['subdivision_number', 'new.subdivision'],
               ['khata_number', 'new.khataNumber'], ['plot_number', 'new.plotNumber'],
               ['flat_number', 'new.flatNumber'], ['village', 'new.village'], ['taluk', 'new.taluk'],
               ['district', 'new.district'], ['state', 'new.state']] as const).map(([key, labelKey]) => (
              <label className="block" key={key}>
                <span className="label">{t(labelKey)}</span>
                <input className="input mt-1" value={form[key]} onChange={set(key)} />
              </label>
            ))}
            <label className="block">
              <span className="label">{t('field.jurisdiction')}</span>
              <select className="input mt-1" value={form.jurisdiction_code} onChange={set('jurisdiction_code')}>
                {(reference.data?.jurisdictions ?? []).map((j) => (
                  <option key={j.code} value={j.code}>{j.name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">{t('new.extent')}</span>
              <input className="input mt-1" type="number" step="any" value={form.land_area_value}
                     onChange={set('land_area_value')} />
            </label>
            <label className="block">
              <span className="label">{t('new.unit')}</span>
              <select className="input mt-1" value={form.land_area_unit} onChange={set('land_area_unit')}>
                {AREA_UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </label>
          </div>
        </Card>

        <Card title={t('new.parties')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="label">{t('field.claimedOwner')}</span>
              <input className="input mt-1" value={form.claimed_owner} onChange={set('claimed_owner')} />
            </label>
            <label className="block">
              <span className="label">{t('field.seller')}</span>
              <input className="input mt-1" value={form.seller_name} onChange={set('seller_name')} />
            </label>
            <label className="block">
              <span className="label">{t('field.buyer')}</span>
              <input className="input mt-1" value={form.buyer_name} onChange={set('buyer_name')} />
            </label>
            <label className="block">
              <span className="label">{t('field.reviewer')}</span>
              <input className="input mt-1" value={form.assigned_reviewer} onChange={set('assigned_reviewer')} />
            </label>
            <label className="block sm:col-span-2">
              <span className="label">{t('new.purpose')}</span>
              <textarea className="input mt-1" rows={2} value={form.purpose} onChange={set('purpose')} />
            </label>
            <label className="block sm:col-span-2">
              <span className="label">{t('new.watchFolder')}</span>
              <input className="input mt-1 font-mono text-[12px]" value={form.watch_folder}
                     onChange={set('watch_folder')} placeholder="/Users/you/Documents/Property/CaseA" />
            </label>
          </div>
        </Card>

        <div className="flex gap-2">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? t('new.creating') : t('new.create')}
          </button>
          <button type="button" className="btn" onClick={() => navigate('/cases')}>{t('common.cancel')}</button>
        </div>
      </form>
    </div>
  )
}
