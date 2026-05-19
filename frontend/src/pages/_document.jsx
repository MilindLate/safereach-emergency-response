import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <link rel="icon" href="/favicon.ico" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="application-name" content="SafeReach" />
        <meta name="description" content="AI-powered emergency response for road accidents — SafeReach" />
        <meta property="og:title" content="SafeReach — Emergency Response" />
        <meta property="og:description" content="AI-powered emergency response. Built by Team CtrlAltElite." />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
