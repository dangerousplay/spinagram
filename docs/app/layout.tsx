import { Inter } from 'next/font/google';
import { Provider } from '@/components/provider';
import './global.css';

const inter = Inter({
  subsets: ['latin'],
});

export const metadata = {
  title: { default: 'spinagram', template: '%s | spinagram' },
  description: 'Diagrams as code, rendered editable to SVG, PNG, PowerPoint and Figma.',
  icons: { icon: `${process.env.NEXT_PUBLIC_BASE_PATH ?? ''}/assets/logo.svg` },
};

export default function Layout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" className={inter.className} suppressHydrationWarning>
      <body className="flex flex-col min-h-screen">
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
