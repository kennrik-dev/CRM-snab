export type Block = 'komplektaciya' | 'zakupka' | 'soprovozhdenie' | 'oplaty' | 'reports' | 'admin'
export type BlockPerms = { view: boolean; edit: boolean }
export type PermMap = Record<Block, BlockPerms>

export function canView(perms: PermMap | null | undefined, block: Block): boolean {
  return perms?.[block]?.view === true
}
export function canEdit(perms: PermMap | null | undefined, block: Block): boolean {
  return perms?.[block]?.edit === true
}
