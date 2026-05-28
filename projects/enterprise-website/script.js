// 平滑滚动
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// 移动端菜单切换
const hamburger = document.querySelector('.hamburger');
const navMenu = document.querySelector('.nav-menu');

hamburger.addEventListener('click', () => {
    navMenu.style.display = navMenu.style.display === 'flex' ? 'none' : 'flex';
    if (navMenu.style.display === 'flex') {
        navMenu.style.position = 'absolute';
        navMenu.style.top = '100%';
        navMenu.style.left = '0';
        navMenu.style.right = '0';
        navMenu.style.background = 'white';
        navMenu.style.flexDirection = 'column';
        navMenu.style.padding = '1rem';
        navMenu.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
    }
});

// 表单提交处理
const contactForm = document.querySelector('.contact-form');
contactForm.addEventListener('submit', (e) => {
    e.preventDefault();
    alert('感谢您的留言！我们会尽快与您联系。');
    contactForm.reset();
});

// CTA 按钮点击
const ctaButton = document.querySelector('.cta-button');
ctaButton.addEventListener('click', () => {
    document.querySelector('#about').scrollIntoView({
        behavior: 'smooth'
    });
});

// 产品按钮点击
document.querySelectorAll('.product-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        alert('产品详情页面开发中...');
    });
});

// 滚动时导航栏阴影效果
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 50) {
        navbar.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
    } else {
        navbar.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
    }
});