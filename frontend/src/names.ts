type Named = { code?: string; name: string; name_en?: string | null }

/** The English name when English is active and one exists, otherwise the main name. */
export function localName(item: Named, lang: string): string {
  return lang.startsWith('en') && item.name_en ? item.name_en : item.name
}

export function accountLabel(item: Named, lang: string): string {
  return `${item.code ?? ''} - ${localName(item, lang)}`
}
