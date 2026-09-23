import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Искра — идеи, которые находят команду', description: 'Платформа, где предприниматели находят студентов для реализации идей.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="ru"><body>{children}</body></html> }
