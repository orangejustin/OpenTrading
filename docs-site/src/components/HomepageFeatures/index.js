import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    icon: '🧠',
    title: 'A prediction desk, not a chatbot',
    description: (
      <>
        Independent forecasters (a rules engine, a logistic model, TimesFM,
        dealer gamma, crowd odds) feed a fusion layer and a bull-vs-bear debate,
        then a learning loop grades every committed call.
      </>
    ),
  },
  {
    icon: '🔒',
    title: 'Keyless & local-first',
    description: (
      <>
        The core needs <strong>no API keys</strong>. Every quote, macro read and
        options chain comes from a small, stdlib-only Python tool you can read.
        Your positions never leave your machine.
      </>
    ),
  },
  {
    icon: '⚖️',
    title: 'Bull vs Bear, with a judge',
    description: (
      <>
        Three LLM calls argue the long and short cases over a frozen evidence
        pack, then a judge commits: a 5-tier verdict with entry, invalidation and
        a time stop — run them all on one model or across several.
      </>
    ),
  },
  {
    icon: '🐋',
    title: 'Smart money, two lenses',
    description: (
      <>
        Contrarian sentiment (Fear &amp; Greed, perp funding) plus on-chain whale
        flow from labeled Ethereum wallets — read live off a public node, no
        account required.
      </>
    ),
  },
  {
    icon: '🌏',
    title: 'Bilingual by design',
    description: (
      <>
        One toggle flips the entire dashboard <em>and</em> the model output
        between English and 简体中文 — the same desk serves a US book and an
        A-share / HK book.
      </>
    ),
  },
  {
    icon: '📈',
    title: 'Options & dealer gamma',
    description: (
      <>
        Signed GEX, call walls and put walls from CBOE chains, fused with
        statistical cones into a confluence ladder — the price levels two
        independent methods both name.
      </>
    ),
  },
];

function Feature({icon, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className={clsx('text--center', styles.featureCard)}>
        <div className={styles.featureIcon}>{icon}</div>
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
