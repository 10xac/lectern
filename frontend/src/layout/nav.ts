import { FileStack, KeyRound, Plug, Settings2, ShieldCheck, Users, type LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  admin?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** The sider's groups. Page paths must not clash with the API's (the server answers /decks itself). */
export const NAV: NavGroup[] = [
  { label: 'Decks', items: [{ to: '/', label: 'Decks', icon: FileStack }] },
  { label: 'People', items: [{ to: '/people/users', label: 'Users', icon: Users, admin: true }] },
  {
    label: 'Connect',
    items: [
      { to: '/connect/tokens', label: 'MCP tokens', icon: KeyRound },
      { to: '/connect/connections', label: 'Connections', icon: Plug },
      { to: '/connect/apps', label: 'OAuth apps', icon: ShieldCheck, admin: true },
    ],
  },
  { label: 'Platform', items: [{ to: '/platform/models', label: 'Models & keys', icon: Settings2, admin: true }] },
];

/** The groups an account sees: admin-only items are dropped for members, and then empty groups. */
export const navFor = (isAdmin: boolean) =>
  NAV.map((g) => ({ ...g, items: g.items.filter((i) => isAdmin || !i.admin) })).filter((g) => g.items.length > 0);

