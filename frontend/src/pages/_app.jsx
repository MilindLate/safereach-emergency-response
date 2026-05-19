/**
 * SafeReach — Next.js App Shell
 * Global styles, Inter font, theme variables.
 */

import Head from "next/head";
import { useEffect } from "react";

export default function SafeReachApp({ Component, pageProps }) {
  useEffect(() => {
    // Restore dispatcher token from localStorage on reload
    const token = localStorage.getItem("safereach_token");
    if (token) pageProps.restoredToken = token;
  }, []);

  return (
    <>
      <Head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#0f172a" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </Head>
      <style global jsx>{`
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { height: 100%; background: #0f172a; color: #e2e8f0; font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased; }
        #__next { height: 100%; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #1e293b; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
        a { color: inherit; text-decoration: none; }
        button { font-family: inherit; }
        input, select, textarea { font-family: inherit; outline: none; }
      `}</style>
      <Component {...pageProps} />
    </>
  );
}
