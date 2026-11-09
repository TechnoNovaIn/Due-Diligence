import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { LanguageProvider } from './i18n'
import CaseWorkspace from './pages/CaseWorkspace'
import Cases from './pages/Cases'
import Dashboard from './pages/Dashboard'
import DocumentViewer from './pages/DocumentViewer'
import NewCase from './pages/NewCase'
import SystemPage from './pages/SystemPage'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <LanguageProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/cases/new" element={<NewCase />} />
          <Route path="/cases/:caseId" element={<Navigate to="overview" replace />} />
          <Route path="/cases/:caseId/:tab" element={<CaseWorkspace />} />
          <Route path="/documents/:documentId" element={<DocumentViewer />} />
          <Route path="/system" element={<SystemPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
      </LanguageProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
