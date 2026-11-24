import type { TFunction } from 'i18next'

import { ApiError, errorMessages } from './client'

/** Readable lines for any failed request: the lock holder, the server's field errors, or a generic text. */
export function apiMessages(e: unknown, t: TFunction): string[] {
  if (!(e instanceof ApiError)) return [t('common.loadFailed')]
  if (e.status === 423) {
    const b = (e.body ?? {}) as { holder?: string; minutes_left?: number }
    return [t('inventory.locked', { holder: b.holder ?? '', minutes: b.minutes_left ?? '' })]
  }
  if (typeof e.body === 'string' && e.body.trimStart().startsWith('<')) return [t('common.loadFailed')] // an HTML error page, not our API
  const lines = errorMessages(e.body)
  return lines.length > 0 ? lines : [t('common.loadFailed')]
}
