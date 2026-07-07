import clsx from 'clsx';
import Heading from '@theme/Heading';
import Translate from '@docusaurus/Translate';
import styles from './styles.module.css';

const FeatureList = [
  {
    icon: '🧠',
    title: <Translate id="feat.desk.title">A prediction desk, not a chatbot</Translate>,
    description: (
      <Translate id="feat.desk.body">
        Independent forecasters (a rules engine, a logistic model, TimesFM,
        dealer gamma, crowd odds) feed a fusion layer and a bull-vs-bear debate,
        then a learning loop grades every committed call.
      </Translate>
    ),
  },
  {
    icon: '🔒',
    title: <Translate id="feat.keyless.title">Keyless & local-first</Translate>,
    description: (
      <Translate id="feat.keyless.body">
        The core needs no API keys. Every quote, macro read and options chain
        comes from a small, stdlib-only Python tool you can read. Your positions
        never leave your machine.
      </Translate>
    ),
  },
  {
    icon: '⚖️',
    title: <Translate id="feat.debate.title">Bull vs Bear, with a judge</Translate>,
    description: (
      <Translate id="feat.debate.body">
        Three LLM calls argue the long and short cases over a frozen evidence
        pack, then a judge commits: a 5-tier verdict with entry, invalidation and
        a time stop — run them all on one model or across several.
      </Translate>
    ),
  },
  {
    icon: '🐋',
    title: <Translate id="feat.smart.title">Smart money, two lenses</Translate>,
    description: (
      <Translate id="feat.smart.body">
        Contrarian sentiment (Fear &amp; Greed, perp funding) plus on-chain whale
        flow from labeled Ethereum wallets — read live off a public node, no
        account required.
      </Translate>
    ),
  },
  {
    icon: '🌏',
    title: <Translate id="feat.bilingual.title">Bilingual by design</Translate>,
    description: (
      <Translate id="feat.bilingual.body">
        One toggle flips the entire dashboard and the model output between
        English and 简体中文 — the same desk serves a US book and an A-share / HK
        book.
      </Translate>
    ),
  },
  {
    icon: '📈',
    title: <Translate id="feat.gamma.title">Options & dealer gamma</Translate>,
    description: (
      <Translate id="feat.gamma.body">
        Signed GEX, call walls and put walls from CBOE chains, fused with
        statistical cones into a confluence ladder — the price levels two
        independent methods both name.
      </Translate>
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
