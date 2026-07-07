import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Translate from '@docusaurus/Translate';
import HomepageFeatures from '@site/src/components/HomepageFeatures';

import Heading from '@theme/Heading';
import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero', styles.heroBanner)}>
      <div className="container">
        <img
          src="img/logo.png"
          alt="OpenTrading"
          className={styles.heroLogo}
        />
        <Heading as="h1" className={styles.heroTitle}>
          {siteConfig.title}
        </Heading>
        <p className={styles.heroSubtitle}>
          <Translate id="home.tagline">
            A local-first, keyless prediction desk for short-term trading
          </Translate>
        </p>
        <p className={styles.heroBlurb}>
          <Translate id="home.blurb">
            Macro-first, risk-first analysis for stocks, options and crypto — run
            entirely on your own machine. No API keys required for the core; every
            number comes from a small, dependency-free tool you can read.
          </Translate>
        </p>
        <div className={styles.buttons}>
          <Link
            className="button button--primary button--lg"
            to="/docs/getting-started">
            <Translate id="home.getStarted">Get started →</Translate>
          </Link>
          <Link
            className="button button--secondary button--lg"
            to="/docs/intro">
            <Translate id="home.whatIsIt">What is it?</Translate>
          </Link>
        </div>
      </div>
    </header>
  );
}

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={siteConfig.title}
      description="A local-first, keyless prediction desk for short-term trading — stocks, options and crypto.">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
