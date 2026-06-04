let category = "all";

function setCategory(cat) {
    category = cat;

    document.querySelectorAll(".cat-chip").forEach(c => c.classList.remove("active"));
    event.target.classList.add("active");

    fetchProducts();
}

document.getElementById("searchInput").addEventListener("input", fetchProducts);

function fetchProducts() {
    const q = document.getElementById("searchInput").value;

    fetch(`/api/search?q=${q}&category=${category}`)
        .then(res => res.json())
        .then(data => {
            const results = document.getElementById("results");
            results.innerHTML = "";

            data.forEach(p => {
                results.innerHTML += `
                    <div class="product-card">
                        <img src="${p[3] || 'https://via.placeholder.com/150'}">
                        <div class="product-info">
                            <h4>${p[1]}</h4>
                            <p>₹${p[2]}</p>
                        </div>
                        <a href="/add_to_cart/${p[0]}">
                            <button class="add-btn">+</button>
                        </a>
                    </div>
                `;
            });
        });
}

// Initial load
fetchProducts();