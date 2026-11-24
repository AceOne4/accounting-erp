import { Component, type ErrorInfo, type ReactNode } from 'react'
import { withTranslation, type WithTranslation } from 'react-i18next'

type Props = { children: ReactNode } & WithTranslation
class Boundary extends Component<Props, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack)
  }
  render() {
    const { t } = this.props
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="mx-auto mt-24 max-w-md rounded-lg border bg-white p-6 text-center">
        <h1 className="mb-2 text-lg font-semibold">{t('error.title')}</h1>
        <p className="mb-4 text-sm text-slate-600">{t('error.body')}</p>
        <button className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white" onClick={() => window.location.assign('/')}>{t('error.reload')}</button>
      </div>
    )
  }
}
const ErrorBoundary = withTranslation()(Boundary)
export default ErrorBoundary
