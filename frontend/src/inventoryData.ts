import { useQuery } from '@tanstack/react-query'

import { api } from './api/client'
import type { PaginatedProductList, Warehouse } from './api/generated'
import { useSession } from './sessionContext'

export type DocLine = { product: string; quantity: string; unit_cost?: string; counted_qty?: string }
export const emptyLine = (): DocLine => ({ product: '', quantity: '', unit_cost: '', counted_qty: '' })

export function useWarehouses() {
  const { company } = useSession()
  return useQuery({ queryKey: ['warehouses', company?.id], queryFn: () => api<Warehouse[]>('/inventory/warehouses/') })
}

export function useProducts() {
  const { company } = useSession()
  return useQuery({
    queryKey: ['products-all', company?.id],
    queryFn: () => api<PaginatedProductList>('/inventory/products/?active=1&page_size=1000'),
  })
}
