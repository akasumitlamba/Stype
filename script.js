// Initialize crisp SVG icons
lucide.createIcons();

// Theme Configuration
const themeToggleBtn = document.getElementById('theme-toggle');
const htmlElement = document.documentElement;

// Check for saved theme preference or use system default
const savedTheme = localStorage.getItem('theme');
if (savedTheme) {
    htmlElement.setAttribute('data-theme', savedTheme);
} else {
    // Check system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    htmlElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
}

// Toggle Theme on Button Click
themeToggleBtn.addEventListener('click', () => {
    const currentTheme = htmlElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    htmlElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
});
