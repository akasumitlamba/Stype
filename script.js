// Initialize Lucide Icons
lucide.createIcons();

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute('href')).scrollIntoView({
            behavior: 'smooth'
        });
    });
});

// Subtle parallax for bento items on mouse move
document.addEventListener('mousemove', (e) => {
    const cards = document.querySelectorAll('.bento-item');
    const x = e.clientX / window.innerWidth;
    const y = e.clientY / window.innerHeight;

    cards.forEach(card => {
        card.style.transform = `translate(${(x - 0.5) * 10}px, ${(y - 0.5) * 10}px)`;
    });
});
