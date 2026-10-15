export default function Home() {
  return (
    <main>
      <section className="hero shell">
        <div className="hero-copy">
          <div className="eyebrow">LIFE TRAJECTORY LAB / 人生轨迹实验室</div>
          <h1>不是“算你会怎样”，<br />而是展开你可能走完的<strong>一生。</strong></h1>
          <p className="lede">
            输入你真实的经历，我们先画出人生轨迹；传统命理只提供明确标注的文化解释，
            历史数据负责接受科学检验。没有经过验证的结论，不会被包装成你的命运概率。
          </p>
          <div className="actions">
            <a className="button primary" href="/analyze">开始推演</a>
            <a className="button ghost" href="/research">看我们怎么验证</a>
          </div>
        </div>
        <div className="orbit-card">
          <div className="orbit-center">命轨</div>
          <span className="orbit o1">出生先验</span>
          <span className="orbit o2">生平校准</span>
          <span className="orbit o3">案例检索</span>
          <span className="orbit o4">未来回测</span>
        </div>
      </section>

      <section className="shell manifesto">
        <article><span>01</span><h2>已然篇</h2><p>从真实人生年表开始，保留当事人提供的每段经历。回顾只算校准，绝不算预测成功。</p></article>
        <article><span>02</span><h2>校准篇</h2><p>用简单问题明确未来关注点。传统命理符号与真实生活数据分开，不把五行直接当成心理测验。</p></article>
        <article><span>03</span><h2>未然篇</h2><p>先展示不同选择对应的未来情景；只有通过独立验证的预测，才允许展示概率和时间范围。</p></article>
      </section>

      <section className="shell split">
        <div>
          <div className="eyebrow">THE RULE</div>
          <h2>大师感在表层，实验室在底层。</h2>
        </div>
        <div className="principles">
          <p><b>命理层</b><span>四柱、十神、大运、流年 → 可追溯的传统解释，未验证前不进入预测概率。</span></p>
          <p><b>个人层</b><span>真实发生过的事件与当前目标 → 构成个人资料，不自动等于统计概率。</span></p>
          <p><b>案例层</b><span>冻结的历史传记数据 → 可重复的事件预测实验，但并不代表一般人群。</span></p>
          <p><b>验证层</b><span>与年龄基线、假命盘比较，外部人群验证，未来预测必须提前锁定。</span></p>
        </div>
      </section>
    </main>
  );
}
