import { useEffect, useState } from 'react'
import { useT } from '../i18n'
import { PlatformApiError, platform } from '../platformClient'
import { routeHref } from '../routing'

type AdminSkillRow = { name: string; path: string }

export function AdminSkillsPage() {
  const t = useT()
  const [items, setItems] = useState<AdminSkillRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setBusy(true)
    platform
      .adminSkills()
      .then((data) => {
        if (!cancelled) setItems(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof PlatformApiError ? err.message : String(err))
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return <p className="auth-error">{error}</p>
  }

  return (
    <div className="panel-page">
      <div className="admin-header">
        <h2>{t('admin.skillsTitle')}</h2>
        <a className="link-btn" href={routeHref('admin')}>
          {t('admin.backToUsers')}
        </a>
      </div>
      <p className="page-hint">{t('admin.skillsHint')}</p>
      <table className="admin-table">
        <thead>
          <tr>
            <th>{t('admin.skillsName')}</th>
            <th>{t('admin.skillsPath')}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.path || row.name}>
              <td>
                <code>{row.name}</code>
              </td>
              <td className="admin-path-cell">{row.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && !busy && (
        <p className="page-hint">{t('admin.skillsEmpty')}</p>
      )}
    </div>
  )
}
