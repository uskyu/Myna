<template>
  <div class="page-shell">
    <header class="topbar">
      <div class="brand">Cloud Portfolio</div>
      <nav class="nav">
        <a href="#about">简介</a>
        <a href="#skills">技术栈</a>
        <a href="#projects">项目</a>
        <a href="#contact">联系</a>
      </nav>
    </header>

    <main>
      <section class="hero section">
        <div class="hero-copy">
          <span class="eyebrow">Cloud Infrastructure · DevOps · Platform Engineering</span>
          <h1>构建稳定、弹性、可观测的现代云基础设施</h1>
          <p class="hero-text">
            我专注于云原生平台、自动化交付与基础设施治理，帮助团队以更高的稳定性、效率与可扩展性推进业务上线。
          </p>
          <div class="hero-actions">
            <a class="btn btn-primary" href="#projects">查看项目</a>
            <a class="btn btn-secondary" href="#contact">联系我</a>
          </div>
          <div class="hero-metrics">
            <div><strong>99.95%</strong><span>平台可用性目标</span></div>
            <div><strong>IaC</strong><span>基础设施标准化交付</span></div>
            <div><strong>CI/CD</strong><span>持续集成与发布自动化</span></div>
          </div>
        </div>
        <div class="hero-visual">
          <div class="glow glow-a"></div>
          <div class="glow glow-b"></div>
          <div class="architecture-card">
            <div class="card-header">
              <span>Cloud Topology</span>
              <span class="status">Healthy</span>
            </div>
            <div class="topology">
              <div class="node node-core">Global LB</div>
              <div class="node-row">
                <div class="node">Kubernetes</div>
                <div class="node">CI/CD</div>
                <div class="node">Observability</div>
              </div>
              <div class="node-row small">
                <div class="node">Terraform</div>
                <div class="node">Helm</div>
                <div class="node">Prometheus</div>
                <div class="node">Grafana</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="about" class="section">
        <div class="section-heading">
          <span>About</span>
          <h2>个人简介</h2>
        </div>
        <div class="about-grid">
          <div class="card">
            <p>
              我是一名聚焦<strong>云计算 / DevOps / 基础设施平台</strong>方向的工程师，关注 Kubernetes、容器平台、
              Infrastructure as Code、自动化交付与可观测性建设。
            </p>
            <p>
              我致力于将复杂系统工程化、标准化，帮助团队构建高可用、可扩展、易维护的云平台能力。
            </p>
          </div>
          <div class="card highlights">
            <div class="highlight-item">
              <h3>平台工程</h3>
              <p>建设统一基础设施能力，提升环境一致性与交付效率。</p>
            </div>
            <div class="highlight-item">
              <h3>自动化治理</h3>
              <p>通过 IaC、流水线与脚本化运维降低人为误差与重复劳动。</p>
            </div>
            <div class="highlight-item">
              <h3>稳定性建设</h3>
              <p>围绕监控、告警、日志与容量规划提升系统可观测性与可靠性。</p>
            </div>
          </div>
        </div>
      </section>

      <section id="skills" class="section">
        <div class="section-heading">
          <span>Stack</span>
          <h2>技能 / 技术栈</h2>
        </div>
        <div class="skills-grid">
          <div class="skill-card">
            <h3>Cloud Platforms</h3>
            <div class="tags">
              <span>AWS</span><span>Azure</span><span>阿里云</span><span>Tencent Cloud</span>
            </div>
          </div>
          <div class="skill-card">
            <h3>Containers & Orchestration</h3>
            <div class="tags">
              <span>Docker</span><span>Kubernetes</span><span>Helm</span><span>Ingress</span>
            </div>
          </div>
          <div class="skill-card">
            <h3>Infrastructure as Code</h3>
            <div class="tags">
              <span>Terraform</span><span>Ansible</span><span>Packer</span><span>GitOps</span>
            </div>
          </div>
          <div class="skill-card">
            <h3>CI/CD</h3>
            <div class="tags">
              <span>GitHub Actions</span><span>GitLab CI</span><span>Jenkins</span><span>Argo CD</span>
            </div>
          </div>
          <div class="skill-card">
            <h3>Observability</h3>
            <div class="tags">
              <span>Prometheus</span><span>Grafana</span><span>Loki</span><span>ELK</span>
            </div>
          </div>
          <div class="skill-card">
            <h3>Languages</h3>
            <div class="tags">
              <span>Python</span><span>Bash</span><span>Go</span><span>YAML</span>
            </div>
          </div>
        </div>
      </section>

      <section id="projects" class="section">
        <div class="section-heading">
          <span>Projects</span>
          <h2>项目经历</h2>
        </div>
        <div class="projects-grid">
          <article class="project-card">
            <h3>Kubernetes 平台搭建与多环境治理</h3>
            <p>设计并落地开发、测试、生产多集群体系，统一命名规范、发布流程与权限管理。</p>
            <ul>
              <li>技术栈：Kubernetes / Helm / Nginx Ingress</li>
              <li>成果：提升环境一致性，缩短服务上线准备周期</li>
            </ul>
          </article>
          <article class="project-card">
            <h3>Terraform 自动化基础设施交付</h3>
            <p>通过模块化 Terraform 管理 VPC、计算、存储与网络资源，实现基础设施版本化与快速复制。</p>
            <ul>
              <li>技术栈：Terraform / Cloud / GitOps</li>
              <li>成果：减少手工配置错误，提升资源交付效率</li>
            </ul>
          </article>
          <article class="project-card">
            <h3>CI/CD 流水线标准化改造</h3>
            <p>构建统一构建、测试、镜像发布与部署流水线，覆盖多服务协同发布场景。</p>
            <ul>
              <li>技术栈：GitLab CI / Jenkins / Docker</li>
              <li>成果：提升发布自动化程度，加快迭代节奏</li>
            </ul>
          </article>
          <article class="project-card">
            <h3>监控告警与可观测平台建设</h3>
            <p>整合指标、日志与告警链路，建立服务健康度视图与故障快速定位能力。</p>
            <ul>
              <li>技术栈：Prometheus / Grafana / Loki / Alertmanager</li>
              <li>成果：增强故障发现与响应效率</li>
            </ul>
          </article>
        </div>
      </section>

      <section id="contact" class="section contact-section">
        <div class="section-heading">
          <span>Contact</span>
          <h2>联系方式</h2>
        </div>
        <div class="contact-card">
          <p>欢迎交流云原生、平台工程、自动化运维与基础设施治理实践。</p>
          <div class="contact-list">
            <a href="mailto:you@example.com">you@example.com</a>
            <a href="https://github.com/yourname" target="_blank" rel="noreferrer">GitHub</a>
            <a href="https://linkedin.com/in/yourname" target="_blank" rel="noreferrer">LinkedIn</a>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <p>© 2025 Cloud Infrastructure Engineer</p>
      <span>Build reliable, scalable and observable platforms.</span>
    </footer>
  </div>
</template>

<script setup>
</script>
