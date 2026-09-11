document.addEventListener("DOMContentLoaded", function () {

    // =========================================================
    // DJANGO MESSAGES AUTO-HIDE
    // =========================================================

    const messages = document.querySelectorAll(".messages .message");

    messages.forEach(function (message) {

        setTimeout(function () {

            message.style.opacity = "0";
            message.style.transform = "translateY(-8px)";

            setTimeout(function () {
                message.remove();
            }, 300);

        }, 3200);

    });


    // =========================================================
    // PRODUCT WISHLIST VISUAL BUTTONS
    // Backend is currently disabled
    // =========================================================

    const wishlistButtons = document.querySelectorAll(
        ".wishlist-btn, .pd-wishlist-btn"
    );

    wishlistButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            button.classList.toggle("is-active");

            const heart =
                button.querySelector(".pd-heart") ||
                button.querySelector("span");

            if (heart) {

                if (button.classList.contains("is-active")) {
                    heart.textContent = "♥";
                } else {
                    heart.textContent = "♡";
                }

            }

        });

    });


    // =========================================================
    // SMOOTH INTERNAL LINKS
    // =========================================================

    const anchorLinks =
        document.querySelectorAll('a[href^="#"]');

    anchorLinks.forEach(function (link) {

        link.addEventListener("click", function (event) {

            const href = link.getAttribute("href");

            if (!href || href === "#") {
                return;
            }

            let target = null;

            try {
                target = document.querySelector(href);
            } catch (error) {
                target = null;
            }

            if (target) {

                event.preventDefault();

                target.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

            }

        });

    });


    // =========================================================
    // HEADER SCROLL STATE
    // =========================================================

    const header =
        document.querySelector(".sw-header");

    if (header) {

        function updateHeader() {

            if (window.scrollY > 20) {
                header.classList.add("is-scrolled");
            } else {
                header.classList.remove("is-scrolled");
            }

        }

        updateHeader();

        window.addEventListener(
            "scroll",
            updateHeader,
            { passive: true }
        );

    }


    // =========================================================
    // LANGUAGE SWITCHER
    // =========================================================

    // Django renders translations and persists language through set_language.

    // =========================================================
    // SOUTHWARD COOKIE CONSENT
    // =========================================================

    const STORAGE_KEY =
        "southward_cookie_consent_v1";


    const banner =
        document.getElementById(
            "swCookieBanner"
        );

    const acceptButton =
        document.getElementById(
            "swCookieAccept"
        );

    const rejectButton =
        document.getElementById(
            "swCookieReject"
        );

    const settingsButton =
        document.getElementById(
            "swCookieSettings"
        );

    const bannerClose =
        document.getElementById(
            "swCookieBannerClose"
        );


    const modalOverlay =
        document.getElementById(
            "swCookieModalOverlay"
        );

    const modalClose =
        document.getElementById(
            "swCookieModalClose"
        );

    const modalReject =
        document.getElementById(
            "swCookieRejectModal"
        );

    const modalSave =
        document.getElementById(
            "swCookieSave"
        );


    const analyticsCheckbox =
        document.getElementById(
            "swConsentAnalytics"
        );

    const marketingCheckbox =
        document.getElementById(
            "swConsentMarketing"
        );


    const footerSettingsButton =
        document.getElementById(
            "swOpenCookieSettings"
        );


    // If cookie HTML does not exist,
    // do not run this section.

    if (!banner || !modalOverlay) {

        console.warn(
            "SOUTHWARD cookie consent HTML not found."
        );

        return;
    }


    // =========================================================
    // READ CONSENT
    // =========================================================

    function getConsent() {

        try {

            const saved =
                localStorage.getItem(
                    STORAGE_KEY
                );

            if (!saved) {
                return null;
            }

            return JSON.parse(saved);

        } catch (error) {

            console.warn(
                "SOUTHWARD consent could not be read.",
                error
            );

            return null;

        }

    }


    // =========================================================
    // OPEN BANNER
    // =========================================================

    function openBanner() {

        banner.classList.add(
            "is-open"
        );

        banner.setAttribute(
            "aria-hidden",
            "false"
        );

    }


    // =========================================================
    // CLOSE BANNER
    // =========================================================

    function closeBanner() {

        banner.classList.remove(
            "is-open"
        );

        banner.setAttribute(
            "aria-hidden",
            "true"
        );

    }


    // =========================================================
    // OPEN SETTINGS
    // =========================================================

    function openModal() {

        const consent =
            getConsent();


        if (analyticsCheckbox) {

            analyticsCheckbox.checked =
                Boolean(
                    consent &&
                    consent.analytics
                );

        }


        if (marketingCheckbox) {

            marketingCheckbox.checked =
                Boolean(
                    consent &&
                    consent.marketing
                );

        }


        modalOverlay.classList.add(
            "is-open"
        );

        modalOverlay.setAttribute(
            "aria-hidden",
            "false"
        );

        document.body.style.overflow =
            "hidden";

    }


    // =========================================================
    // CLOSE SETTINGS
    // =========================================================

    function closeModal() {

        modalOverlay.classList.remove(
            "is-open"
        );

        modalOverlay.setAttribute(
            "aria-hidden",
            "true"
        );

        document.body.style.overflow =
            "";

    }


    // =========================================================
    // SAVE CONSENT
    // =========================================================

    function saveConsent(settings) {

        const consent = {

            essential: true,

            analytics:
                Boolean(
                    settings.analytics
                ),

            marketing:
                Boolean(
                    settings.marketing
                ),

            savedAt:
                new Date().toISOString()

        };


        try {

            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify(consent)
            );

        } catch (error) {

            console.warn(
                "SOUTHWARD consent could not be saved.",
                error
            );

        }


        window.SouthwardConsent =
            consent;


        document.dispatchEvent(

            new CustomEvent(
                "southward:consent-changed",
                {
                    detail: consent
                }
            )

        );


        closeBanner();
        closeModal();

    }


    // =========================================================
    // FIRST VISIT
    // =========================================================

    const existingConsent =
        getConsent();


    if (!existingConsent) {

        window.setTimeout(
            function () {

                openBanner();

            },
            450
        );

    } else {

        window.SouthwardConsent =
            existingConsent;

    }


    // =========================================================
    // ACCEPT ALL
    // =========================================================

    if (acceptButton) {

        acceptButton.addEventListener(
            "click",
            function () {

                saveConsent({
                    analytics: true,
                    marketing: true
                });

            }
        );

    }


    // =========================================================
    // REJECT OPTIONAL
    // =========================================================

    if (rejectButton) {

        rejectButton.addEventListener(
            "click",
            function () {

                saveConsent({
                    analytics: false,
                    marketing: false
                });

            }
        );

    }


    if (modalReject) {

        modalReject.addEventListener(
            "click",
            function () {

                if (analyticsCheckbox) {
                    analyticsCheckbox.checked =
                        false;
                }

                if (marketingCheckbox) {
                    marketingCheckbox.checked =
                        false;
                }


                saveConsent({
                    analytics: false,
                    marketing: false
                });

            }
        );

    }


    // =========================================================
    // BANNER COOKIE SETTINGS
    // =========================================================

    if (settingsButton) {

        settingsButton.addEventListener(
            "click",
            function () {

                closeBanner();
                openModal();

            }
        );

    }


    // =========================================================
    // FOOTER COOKIE SETTINGS
    // =========================================================

    if (footerSettingsButton) {

        footerSettingsButton.addEventListener(
            "click",
            function () {

                openModal();

            }
        );

    }


    // =========================================================
    // SAVE CUSTOM SETTINGS
    // =========================================================

    if (modalSave) {

        modalSave.addEventListener(
            "click",
            function () {

                saveConsent({

                    analytics:
                        analyticsCheckbox
                            ? analyticsCheckbox.checked
                            : false,

                    marketing:
                        marketingCheckbox
                            ? marketingCheckbox.checked
                            : false

                });

            }
        );

    }


    // =========================================================
    // BANNER X
    // =========================================================

    if (bannerClose) {

        bannerClose.addEventListener(
            "click",
            function () {

                closeBanner();

            }
        );

    }


    // =========================================================
    // MODAL X
    // =========================================================

    if (modalClose) {

        modalClose.addEventListener(
            "click",
            function () {

                closeModal();

            }
        );

    }


    // =========================================================
    // CLICK OUTSIDE MODAL
    // =========================================================

    modalOverlay.addEventListener(
        "click",
        function (event) {

            if (
                event.target ===
                modalOverlay
            ) {

                closeModal();

            }

        }
    );


    // =========================================================
    // ESCAPE
    // =========================================================

    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key ===
                "Escape"
            ) {

                closeModal();

            }

        }
    );

});