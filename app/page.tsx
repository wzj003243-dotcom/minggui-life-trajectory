export default function Home() {
  return (
    <main>
      <section className="hero shell">
        <div className="hero-copy">
          <div className="eyebrow">LIFE TRAJECTORY LAB / 人生轨迹实验室</div>
          <h1>不是“算你会怎样”，<br />而是展开你可能走完的<strong>一生。</strong></h1>
          <p className="lede">
            命轨把传统八字当作低置信度先验，用已经发生的人生事件校准个体画像，
            再用大规模人物生平数据寻找相似轨迹。过去用于校准，未来必须提前锁定并接受回测。
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
        <article><span>01</span><h2>已然篇</h2><p>先用传统命理解释过去，再逐条核对。命中的规则升权，没命中的规则降权，不把事后解释冒充预测。</p></article>
        <article><span>02</span><h2>校准篇</h2><p>用少量高信息量问题把“水旺、火弱、冲多”等传统标签翻译成真实行为模式与现实约束。</p></article>
        <article><span>03</span><h2>未然篇</h2><p>模型展开 3–5 条人生分支，给出年龄阶段、关键节点、机会与风险；每条预测都有时间戳与验证标准。</p></article>
      </section>

      <section className="shell split">
        <div>
          <div className="eyebrow">THE RULE</div>
          <h2>大师感在表层，实验室在底层。</h2>
        </div>
        <div className="principles">
          <p><b>命理层</b><span>四柱、五行、十神、大运、流年 → 只生成先验。</span></p>
          <p><b>个人层</b><span>早年事件、行为模式、资源与价值排序 → 收束到具体的人。</span></p>
          <p><b>案例层</b><span>Wikidata / Pantheon / biographies → 学习人生轨迹而不是背名人。</span></p>
          <p><b>验证层</b><span>现实 baseline、假生日、时间切分、预测账本 → 错了就记错。</span></p>
        </div>
      </section>
    </main>
  );
}
