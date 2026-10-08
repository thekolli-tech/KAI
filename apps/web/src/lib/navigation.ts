import {
  BotIcon,
  FolderKanbanIcon,
  LibraryIcon,
  MessageSquareIcon,
  PlusIcon,
  SettingsIcon,
  WrenchIcon,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export const primaryNav: NavItem[] = [
  { href: "/", label: "New Chat", icon: PlusIcon },
  { href: "/chats", label: "Chats", icon: MessageSquareIcon },
  { href: "/projects", label: "Projects", icon: FolderKanbanIcon },
  { href: "/knowledge", label: "Knowledge", icon: LibraryIcon },
  { href: "/agents", label: "Agents", icon: BotIcon },
  { href: "/tools", label: "Tools", icon: WrenchIcon },
];

export const settingsNav: NavItem = {
  href: "/settings",
  label: "Settings",
  icon: SettingsIcon,
};
