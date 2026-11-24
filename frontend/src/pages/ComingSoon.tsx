import { useTranslation } from 'react-i18next'

export default function ComingSoon({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation()
  return (
    <section>
      <h2 className="text-xl font-semibold">{t(titleKey)}</h2>
      <p className="mt-2 text-slate-600">{t('common.comingSoon')}</p>
    </section>
  )
}
