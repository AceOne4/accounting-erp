import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

export default function NotFound() {
  const { t } = useTranslation()
  return (
    <div className="py-16 text-center">
      <h2 className="mb-2 text-xl font-semibold">{t('notFound.title')}</h2>
      <Link className="underline" to="/">{t('notFound.home')}</Link>
    </div>
  )
}
