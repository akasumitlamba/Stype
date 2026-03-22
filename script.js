// Initialize crisp SVG icons
lucide.createIcons();

// Theme Configuration
const themeToggleBtn = document.getElementById('theme-toggle');
const htmlElement = document.documentElement;

// Check for saved theme preference
const savedTheme = localStorage.getItem('theme');

// Apply saved theme if it exists, otherwise Default to Light
if (savedTheme) {
    htmlElement.setAttribute('data-theme', savedTheme);
} else {
    // Force Light Theme default as requested
    htmlElement.setAttribute('data-theme', 'light');
    localStorage.setItem('theme', 'light');
}

// Toggle Theme on Button Click
themeToggleBtn.addEventListener('click', () => {
    const currentTheme = htmlElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    htmlElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
});
