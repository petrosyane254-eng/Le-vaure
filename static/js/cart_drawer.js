(() => {
    const drawer = document.getElementById("swCartDrawer");
    const overlay = document.getElementById("swCartDrawerOverlay");

    if (!drawer || !overlay) {
        console.error("SOUTHWARD cart drawer HTML not found.");
        return;
    }

    const closeBtn = document.getElementById("swCartDrawerClose");
    const continueBtn = document.getElementById("swCartDrawerContinue");

    const image = document.getElementById("swCartDrawerImage");
    const productLink = document.getElementById("swCartDrawerProductLink");
    const nameLink = document.getElementById("swCartDrawerName");
    const category = document.getElementById("swCartDrawerCategory");
    const price = document.getElementById("swCartDrawerPrice");

    const quantityEl = document.getElementById("swCartDrawerQuantity");
    const total = document.getElementById("swCartDrawerTotal");

    const plus = document.getElementById("swCartDrawerPlus");
    const minus = document.getElementById("swCartDrawerMinus");
    const remove = document.getElementById("swCartDrawerRemove");

    const itemBox = document.getElementById("swCartDrawerItem");

    let currentProduct = null;


    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(";") : [];

        for (let cookie of cookies) {
            cookie = cookie.trim();

            if (cookie.startsWith(name + "=")) {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }

        return "";
    }


    function openDrawer() {
        overlay.hidden = false;

        requestAnimationFrame(() => {
            overlay.classList.add("is-open");
            drawer.classList.add("is-open");
        });

        drawer.setAttribute("aria-hidden", "false");

        document.body.classList.add("sw-cart-drawer-open");
    }


    function closeDrawer() {
        overlay.classList.remove("is-open");
        drawer.classList.remove("is-open");

        drawer.setAttribute("aria-hidden", "true");

        document.body.classList.remove("sw-cart-drawer-open");

        setTimeout(() => {
            overlay.hidden = true;
        }, 280);
    }


    function updateCartBadge(count) {
        const cartButton = document.querySelector(".sw-cart-btn");

        if (!cartButton) return;

        let badge = cartButton.querySelector(".sw-cart-count");

        if (Number(count) > 0) {

            if (!badge) {
                badge = document.createElement("span");
                badge.className = "sw-cart-count";
                cartButton.appendChild(badge);
            }

            badge.textContent = count;

        } else if (badge) {
            badge.remove();
        }
    }


    function renderDrawer(data) {

        if (!data || !data.product) {
            console.error("Invalid cart response:", data);
            return;
        }

        currentProduct = data.product;

        if (image) {
            image.src = currentProduct.image || image.src;

            image.alt = currentProduct.name;
        }

        if (productLink) {
            productLink.href = currentProduct.product_url;
        }

        if (nameLink) {
            nameLink.href = currentProduct.product_url;
            nameLink.textContent = currentProduct.name;
        }

        if (category) {
            category.textContent =
                currentProduct.category || "SOUTHWARD";
        }

        if (price) {
            price.textContent = `$${currentProduct.price}`;
        }

        if (quantityEl) {
            quantityEl.textContent = currentProduct.quantity;
        }

        if (total) {
            total.textContent = `$${data.cart_total}`;
        }

        updateCartBadge(data.cart_count);

        if (itemBox) {
            itemBox.style.display =
                Number(currentProduct.quantity) > 0
                    ? "grid"
                    : "none";
        }
    }


    async function updateQuantity(quantity) {

        if (!currentProduct) return;

        const body = new URLSearchParams();

        body.set(
            "quantity",
            Math.max(0, Number(quantity))
        );

        const response = await fetch(
            currentProduct.update_url,
            {
                method: "POST",

                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "Content-Type":
                        "application/x-www-form-urlencoded;charset=UTF-8",
                },

                body: body.toString(),
            }
        );

        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(
                data.message || "Cart update failed."
            );
        }

        renderDrawer(data);
    }


    document.addEventListener(
        "submit",
        async function (event) {

            const form = event.target.closest(
                ".pd-buy, .quick-add-form, .swh-quick-add, form[data-cart-add]"
            );

            if (!form) return;

            event.preventDefault();

            const submitButton =
                event.submitter ||
                form.querySelector(
                    'button[type="submit"]'
                );

            if (submitButton) {
                submitButton.disabled = true;
            }

            try {

                const formData = new FormData(form);

                const response = await fetch(
                    form.action,
                    {
                        method: "POST",

                        headers: {
                            "X-Requested-With":
                                "XMLHttpRequest",
                        },

                        body: formData,
                    }
                );


                const contentType =
                    response.headers.get(
                        "content-type"
                    ) || "";


                if (
                    !contentType.includes(
                        "application/json"
                    )
                ) {
                    throw new Error(
                        "Server did not return JSON."
                    );
                }


                const data =
                    await response.json();


                if (!response.ok || !data.ok) {

                    throw new Error(
                        data.message ||
                        "Could not add product."
                    );
                }


                renderDrawer(data);

                openDrawer();

            } catch (error) {

                console.error(
                    "SOUTHWARD CART ERROR:",
                    error
                );

                form.submit();

            } finally {

                if (submitButton) {
                    submitButton.disabled = false;
                }
            }
        }
    );


    if (plus) {
        plus.addEventListener(
            "click",
            async function () {

                if (!currentProduct) return;

                const current =
                    Number(
                        currentProduct.quantity || 0
                    );

                const stock =
                    Number(
                        currentProduct.stock || 0
                    );

                if (current >= stock) return;

                try {

                    await updateQuantity(
                        current + 1
                    );

                } catch (error) {

                    console.error(error);
                }
            }
        );
    }


    if (minus) {
        minus.addEventListener(
            "click",
            async function () {

                if (!currentProduct) return;

                const current =
                    Number(
                        currentProduct.quantity || 0
                    );

                try {

                    await updateQuantity(
                        current - 1
                    );

                } catch (error) {

                    console.error(error);
                }
            }
        );
    }


    if (remove) {
        remove.addEventListener(
            "click",
            async function () {

                if (!currentProduct) return;

                try {

                    await updateQuantity(0);

                } catch (error) {

                    console.error(error);
                }
            }
        );
    }


    if (closeBtn) {
        closeBtn.addEventListener(
            "click",
            closeDrawer
        );
    }


    if (continueBtn) {
        continueBtn.addEventListener(
            "click",
            closeDrawer
        );
    }


    overlay.addEventListener(
        "click",
        closeDrawer
    );


    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Escape" &&
                drawer.classList.contains(
                    "is-open"
                )
            ) {
                closeDrawer();
            }
        }
    );
})();
