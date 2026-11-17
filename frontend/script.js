document.addEventListener("DOMContentLoaded", () => {
    const $ = (id) => document.getElementById(id);

    const runButton = $("runResearchBtn");
    const papersContainer = $("papersContainer");
    const insightsContainer = $("insightsContainer");
    const ideasContainer = $("ideasContainer");
    const conferencesContainer = $("conferencesContainer");
    const deadlinesContainer = $("deadlinesContainer");

    // Safely display text
    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]);
    }

    function safeLink(url) {
        try {
            const parsed = new URL(url, window.location.origin);
            return ["http:", "https:"].includes(parsed.protocol)
                ? parsed.href : "";
        } catch {
            return "";
        }
    }

    function formatDate(value) {
        if (!value) return "Date not listed";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return String(value);
        }

        return date.toLocaleDateString("en", {
            day: "numeric",
            month: "short",
            year: "numeric"
        });
    }

    function formatTimestamp(isoString) {
        if (!isoString) {
            return new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit"
            });
        }
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return String(isoString);

        return date.toLocaleDateString("en", {
            month: "short",
            day: "numeric"
        }) + ", " + date.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
        });
    }

    function loading(message) {
        return `<div class="loading-state">
            <i class="fa-solid fa-spinner fa-spin"></i>
            ${escapeHTML(message)}
        </div>`;
    }

    function empty(icon, title, message) {
        return `<div class="empty-state">
            <i class="fa-solid ${icon}"></i>
            <h3>${escapeHTML(title)}</h3>
            <p>${escapeHTML(message)}</p>
        </div>`;
    }

    function showToast(message) {
        let toast = $("radarToast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "radarToast";
            Object.assign(toast.style, {
                position: "fixed",
                bottom: "24px",
                right: "24px",
                background: "#1f2937",
                color: "#ffffff",
                padding: "12px 18px",
                borderRadius: "10px",
                fontSize: "0.9rem",
                fontWeight: "500",
                boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
                zIndex: "9999",
                transition: "opacity 0.25s ease"
            });
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.opacity = "1";
        toast.hidden = false;

        clearTimeout(toast._hideTimer);
        toast._hideTimer = setTimeout(() => {
            toast.style.opacity = "0";
            setTimeout(() => { toast.hidden = true; }, 250);
        }, 3000);
    }

    function markdown(text) {
        if (window.marked && window.DOMPurify) {
            return DOMPurify.sanitize(marked.parse(String(text || "")));
        }

        return `<p>${escapeHTML(text)}</p>`;
    }

    // ------------------------------------
    // 1. RESEARCH PAPER CARDS
    // ------------------------------------

    function createPaperCard(paper, index) {
        const category = paper.publication_category ||
                         paper.type || "Publication";

        const isConference =
            String(category).toLowerCase().includes("conference");

        const link = safeLink(
            paper.doi || paper.url || paper.link
        );

        return `
        <article class="info-card paper-card accent-${isConference ? "coral" : "blue"}">

            <div class="card-topline">
                <span class="badge ${isConference ? "badge-coral" : "badge-blue"}">
                    ${escapeHTML(category)}
                </span>
                <span class="card-index">PAPER ${index + 1}</span>
            </div>

            <h3>${escapeHTML(paper.title || "Untitled paper")}</h3>

            <p class="card-meta">
                Year: ${escapeHTML(paper.year ?? "N/A")}
                · Citations: ${escapeHTML(paper.citations ?? 0)}
            </p>

            <div class="card-actions">
                ${link
                    ? `<a class="card-link" href="${escapeHTML(link)}"
                         target="_blank" rel="noopener noreferrer">
                         Read paper <i class="fa-solid fa-arrow-up-right-from-square"></i>
                       </a>`
                    : `<span class="muted-note">No paper link available</span>`
                }
            </div>

        </article>`;
    }

    // ------------------------------------
    // 2. EXTRACT AI REPORT SECTIONS
    // ------------------------------------

    function extractSections(report) {
        const text = String(report || "");

        const headings = [
            ...text.matchAll(/^#{1,3}\s+(.+?)\s*$/gm)
        ];

        return headings.map((heading, index) => {
            const start = heading.index + heading[0].length;

            const end = index + 1 < headings.length
                ? headings[index + 1].index
                : text.length;

            return {
                title: heading[1].replace(/[*_`]/g, "").trim(),
                body: text.slice(start, end).trim()
            };
        }).filter(section => section.body);
    }

    // ------------------------------------
    // 3. INSIGHT CARDS
    // ------------------------------------

    function createInsightCard(section, type, index) {
        const colors = {
            gap: "purple",
            trend: "teal",
            insight: "blue"
        };

        const color = colors[type] || "blue";

        return `
        <article class="info-card insight-card accent-${color}">

            <div class="card-topline">
                <span class="badge badge-${color}">
                    ${type === "gap" ? "RESEARCH GAP" :
                      type === "trend" ? "RESEARCH TREND" : "AI INSIGHT"}
                </span>

                <span class="card-index">${index + 1}</span>
            </div>

            <h3>${escapeHTML(section.title)}</h3>

            <div class="markdown-content">
                ${markdown(section.body)}
            </div>

            <button class="text-button expand-card">
                Read details <i class="fa-solid fa-arrow-right"></i>
            </button>

            <div class="full-content" hidden>
                ${markdown(section.body)}
            </div>

        </article>`;
    }

    // ------------------------------------
    // 4. SUGGESTED RESEARCH IDEA CARDS
    // ------------------------------------

    function createIdeaCard(section, index) {
        return `
        <article class="info-card idea-card accent-amber">

            <div class="card-topline">
                <span class="badge badge-amber">
                    SUGGESTED RESEARCH IDEA
                </span>

                <span class="card-index">IDEA ${index + 1}</span>
            </div>

            <h3>${escapeHTML(section.title)}</h3>

            <div class="markdown-content">
                ${markdown(section.body)}
            </div>

            <button class="text-button expand-card">
                Read details <i class="fa-solid fa-arrow-right"></i>
            </button>

            <div class="full-content" hidden>
                ${markdown(section.body)}
            </div>

        </article>`;
    }

    // ------------------------------------
    // 5. DISPLAY RESEARCH RESULTS
    // ------------------------------------

    function displayResearch(data) {
        const papers = Array.isArray(data.papers)
            ? data.papers : [];

        $("papersCount").textContent = papers.length;
        $("paperResultCount").textContent = `${papers.length} papers`;

        const conferencePapers = papers.filter(p =>
            String(p.publication_category || "").toLowerCase() === "conference"
            || p.type === "conference-paper"
        ).length;

        const journalPapers = papers.filter(p =>
            String(p.publication_category || "").toLowerCase() === "journal"
            || p.type === "article"
        ).length;

        const alertBox = $("publicationAlert");

        const waBadge = data.whatsapp_status === "sent"
            ? `<span class="badge badge-green" style="margin-left: 8px;"><i class="fa-brands fa-whatsapp"></i> WhatsApp Briefing Sent</span>`
            : data.whatsapp_status === "failed"
                ? `<span class="badge badge-coral" style="margin-left: 8px;"><i class="fa-brands fa-whatsapp"></i> WhatsApp Failed</span>`
                : "";

        const triggerBadge = data.trigger_type === "weekly_auto"
            ? `<span class="badge badge-blue" style="margin-left: 6px;">Weekly Scheduled Update</span>`
            : `<span class="badge badge-amber" style="margin-left: 6px;">Voluntary Daily Run</span>`;

        const rateLimitNotice = data.status === "rate_limited"
            ? `<div style="margin-top: 6px; font-weight: 600; color: #9a3d1e;">
                 <i class="fa-solid fa-circle-info"></i> ${escapeHTML(data.message || "Daily voluntary limit reached (max 1 manual run per day).")}
               </div>`
            : "";

        alertBox.innerHTML = `
            <strong>Research Publication Alert ${waBadge} ${triggerBadge}</strong>
            <span>
                ${conferencePapers} conference papers and
                ${journalPapers} journal articles identified.
            </span>
            ${rateLimitNotice}
        `;

        alertBox.hidden = false;

        // Papers
        papersContainer.innerHTML = papers.length
            ? papers.map(createPaperCard).join("")
            : empty("fa-book-open", "No papers found", "No papers were returned.");

        // Analyze report headings
        const sections = extractSections(data.analysis);

        const gaps = sections.filter(s =>
            /gap|limitation|challenge/i.test(s.title)
        );

        const trends = sections.filter(s =>
            /trend|emerging|theme/i.test(s.title)
        );

        const ideas = sections.filter(s =>
            /idea|proposal|proposed|research direction/i.test(s.title)
        );

        // Research gaps and trends
        const insights = [...gaps, ...trends];

        insightsContainer.innerHTML = insights.length
            ? insights.map((s, i) =>
                createInsightCard(
                    s,
                    gaps.includes(s) ? "gap" : "trend",
                    i
                )
              ).join("")
            : empty(
                "fa-brain",
                "No separate insights found",
                "Check the AI report headings."
              );

        // Suggested ideas
        ideasContainer.innerHTML = ideas.length
            ? ideas.map(createIdeaCard).join("")
            : empty(
                "fa-lightbulb",
                "No separate research ideas found",
                "The report may use a different heading."
              );

        $("trendsCount").textContent = trends.length;
        $("ideasCount").textContent = ideas.length;
     

        const formattedTime = formatTimestamp(data.last_updated);
        $("lastAnalysis").textContent = formattedTime;

        const btnRefreshEl = $("buttonLastRefresh");
        if (btnRefreshEl) {
            const modeLabel = data.trigger_type === "weekly_auto" ? "Weekly auto" : "Manual";
            btnRefreshEl.textContent = `Last refreshed: ${formattedTime} (${modeLabel})`;
        }

    }

    // ------------------------------------
    // 6. LOAD SAVED LATEST WEEKLY/DAILY ANALYSIS
    // ------------------------------------

 

    async function loadLatestResearch() {
        try {
            const response = await fetch("/api/research/latest", { cache: "no-store" });
            if (!response.ok) return;

            const data = await response.json();
            if (data && data.status !== "empty" && data.analysis) {
                displayResearch(data);
            }
        } catch (error) {
            console.warn("Could not load cached research:", error);
        }
    }

    // ------------------------------------
    // 7. CONFERENCE CARDS
    // ------------------------------------

    function rankingText(rankings) {
        if (!rankings || typeof rankings !== "object") {
            return "Ranking not listed";
        }

        const entries = Object.entries(rankings)
            .filter(([key, value]) =>
                value && !["N", "N/A", "null"].includes(String(value))
            );

        return entries.length
            ? entries.map(([key, value]) =>
                `${key.toUpperCase()}: ${value}`
              ).join(" · ")
            : "Ranking not listed";
    }

    function createConferenceCard(item, index) {
        const title = item.title || item.name || "Conference";

        const date = item.start ||
                     item.event_start ||
                     item.conference_date;

        const location = [
            item.city,
            item.country
        ].filter(Boolean).join(", ") ||
          item.location ||
          "Location not listed";

        const link = safeLink(
            item.website || item.link || item.url
        );

        const colors = ["blue", "purple", "teal", "coral"];
        const color = colors[index % colors.length];

        const status = item.submission_status || "Upcoming event";

        const statusClass = /passed/i.test(status)
            ? "badge-muted" : "badge-green";

        return `
        <article class="info-card conference-card accent-${color}">

            <div class="card-topline">
                <span class="badge badge-${color}">
                    CONFERENCE
                </span>

                <span class="badge ${statusClass}">
                    ${escapeHTML(status)}
                </span>
            </div>

            <h3>
                ${escapeHTML(title)}
                ${item.year ? `<span class="year-label">${escapeHTML(item.year)}</span>` : ""}
            </h3>

            <p class="conference-detail">
                <i class="fa-regular fa-calendar"></i>
                ${escapeHTML(formatDate(date))}
                ${item.end ? ` – ${escapeHTML(formatDate(item.end))}` : ""}
            </p>

            <p class="conference-detail">
                <i class="fa-solid fa-location-dot"></i>
                ${escapeHTML(location)}
            </p>

            <p class="conference-detail">
                <i class="fa-solid fa-award"></i>
                ${escapeHTML(rankingText(item.rankings || item.ranking))}
            </p>

            <div class="card-actions">
                ${link
                    ? `<a class="card-link" href="${escapeHTML(link)}"
                         target="_blank" rel="noopener noreferrer">
                         Official website
                         <i class="fa-solid fa-arrow-up-right-from-square"></i>
                       </a>`
                    : `<span class="muted-note">Official link unavailable</span>`
                }
            </div>

        </article>`;
    }

    // ------------------------------------
    // 8. CFP DEADLINE CARDS
    // ------------------------------------

    function createDeadlineCard(item) {
        const title = item.title || item.name || "Conference CFP";

        const deadline = item.deadline ||
                         item.submission_deadline ||
                         item.date;

        const link = safeLink(
            item.website || item.link || item.url
        );

        const date = deadline ? new Date(deadline) : null;

        const days = date && !Number.isNaN(date.getTime())
            ? Math.ceil((date - new Date()) / 86400000)
            : null;

        const urgency = days !== null && days <= 7
            ? "urgent"
            : days !== null && days <= 30
                ? "soon"
                : "normal";

        const label = days !== null && days < 0
            ? "Passed"
            : days !== null && days <= 7
                ? "Due soon"
                : "Open deadline";

        const badge = urgency === "urgent"
            ? "badge-coral"
            : urgency === "soon"
                ? "badge-amber"
                : "badge-green";

        return `
        <article class="info-card deadline-card deadline-${urgency}">

            <div class="card-topline">
                <span class="badge badge-blue">CALL FOR PAPERS</span>
                <span class="badge ${badge}">${label}</span>
            </div>

            <h3>
                ${escapeHTML(title)}
                ${item.year ? `<span class="year-label">${escapeHTML(item.year)}</span>` : ""}
            </h3>

            <p class="deadline-date">
                <i class="fa-regular fa-clock"></i>
                ${escapeHTML(formatDate(deadline))}
            </p>

            <p class="conference-detail">
                ${escapeHTML(item.deadline_type || item.type || "Submission")} deadline
            </p>

            ${days !== null && days >= 0
                ? `<p class="days-left">
                    ${days === 0 ? "Deadline is today" : `${days} days remaining`}
                   </p>`
                : ""
            }

            <div class="card-actions">
                ${link
                    ? `<a class="card-link" href="${escapeHTML(link)}"
                         target="_blank" rel="noopener noreferrer">
                         Conference details
                         <i class="fa-solid fa-arrow-up-right-from-square"></i>
                       </a>`
                    : ""
                }
            </div>

        </article>`;
    }

    // ------------------------------------
    // 9. COMPACT HOT DATES CARD & CONFERENCE LOADER
    // ------------------------------------

    function renderHotDatesCard(deadlines) {
        const container = $("hotDeadlinesSummary");
        if (!container) return;

        // Prioritize high-relevance venues (score >= 80) sorted by earliest deadline
        const sorted = [...deadlines].sort((a, b) => {
            const scoreDiff = (b.relevance?.relevance_score || 0) - (a.relevance?.relevance_score || 0);
            if (scoreDiff !== 0) return scoreDiff;
            return String(a.deadline || "9999").localeCompare(String(b.deadline || "9999"));
        });

        const topItems = sorted.slice(0, 4);

        if (!topItems.length) {
            container.innerHTML = `<p class="muted-note">No upcoming priority deadlines found. Click "View all conferences &amp; dates" to check the calendar.</p>`;
            return;
        }

        container.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem;">
                ${topItems.map(item => {
                    const deadline = item.deadline || item.submission_deadline || item.date;
                    const dateObj = deadline ? new Date(deadline) : null;
                    const days = dateObj && !Number.isNaN(dateObj.getTime())
                        ? Math.ceil((dateObj - new Date()) / 86400000)
                        : null;
                    const link = safeLink(item.website || item.link || item.url);

                    return `
                    <div style="padding: 0.75rem 0.9rem; border: 1px solid #e5e7eb; border-radius: 10px; background: #fafafa;">
                        <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem;">
                            <strong style="font-size: 0.95rem;">
                                ${link
                                    ? `<a href="${escapeHTML(link)}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none;">${escapeHTML(item.title || "Conference")}</a>`
                                    : escapeHTML(item.title || "Conference")
                                }
                            </strong>
                            ${days !== null && days >= 0
                                ? `<span class="badge ${days <= 14 ? "badge-coral" : "badge-amber"}" style="font-size: 0.72rem; white-space: nowrap;">${days}d left</span>`
                                : ""
                            }
                        </div>
                        <div style="font-size: 0.82rem; color: #4b5563; margin-top: 0.3rem;">
                            <i class="fa-regular fa-clock"></i> ${escapeHTML(formatDate(deadline))}
                            ${item.deadline_type ? `· ${escapeHTML(item.deadline_type === "paper" ? "Full paper due" : item.deadline_type)}` : ""}
                        </div>
                    </div>`;
                }).join("")}
            </div>
        `;
    }

    async function loadConferences() {
        conferencesContainer.innerHTML =
            loading("Loading conferences...");

        deadlinesContainer.innerHTML =
            loading("Loading CFP deadlines...");

        try {
            const response = await fetch("/api/conferences");

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Research API Error: ${response.status}`);
            }


            const data = await response.json();

            if (data.detail || data.status === "error") {
                throw new Error(data.detail || "Research agent failed.");
            }


            const conferences = Array.isArray(data.upcoming_conferences)
                ? data.upcoming_conferences : [];

            const deadlines = Array.isArray(data.upcoming_cfp_deadlines)
                ? data.upcoming_cfp_deadlines : [];

            $("cfpCount").textContent = deadlines.length;

            $("conferencesSummary").textContent =
                `${conferences.length} upcoming events · ${deadlines.length} upcoming CFP deadlines`;

            // Populate the single compact card on the Dashboard
            renderHotDatesCard(deadlines);

            // Populate the full secondary tab
            conferencesContainer.innerHTML = conferences.length
                ? conferences.map(createConferenceCard).join("")
                : empty(
                    "fa-calendar-xmark",
                    "No upcoming conferences",
                    "No matching events found."
                );

            deadlinesContainer.innerHTML = deadlines.length
                ? deadlines.map(createDeadlineCard).join("")
                : empty(
                    "fa-hourglass-end",
                    "No upcoming deadlines",
                    "No future submission deadlines found."
                );

        } catch (error) {
            console.error("Conference error:", error);

            if ($("hotDeadlinesSummary")) {
                $("hotDeadlinesSummary").innerHTML =
                    `<p class="muted-note">Could not load priority deadlines (${escapeHTML(error.message)}).</p>`;
            }

            conferencesContainer.innerHTML =
                empty("fa-triangle-exclamation", "Could not load conferences", error.message);

            deadlinesContainer.innerHTML =
                empty("fa-triangle-exclamation", "Could not load deadlines", error.message);
        }
    }

    // ------------------------------------
    // 10. RUN RESEARCH AGENT (VOLUNTARY DAILY TRIGGER)
    // ------------------------------------

    runButton.addEventListener("click", async () => {
        runButton.disabled = true;

        runButton.innerHTML =
            '<i class="fa-solid fa-spinner fa-spin"></i> Running Research Agent...';

        papersContainer.innerHTML = loading("Searching academic papers...");
        insightsContainer.innerHTML = loading("Analyzing research...");
        ideasContainer.innerHTML = loading("Generating research ideas...");

        $("publicationAlert").hidden = true;

        try {
            const response = await fetch("/api/research/run", {
                method: "POST"
            });

            if (!response.ok) {
                throw new Error(`Research API Error: ${response.status}`);
            }

            const data = await response.json();

            if (data.detail || data.status === "error") {
                throw new Error(data.detail || "Research agent failed.");
            }

            displayResearch(data);

        } catch (error) {
            console.error("ResearchRadar error:", error);

            papersContainer.innerHTML =
                empty("fa-triangle-exclamation", "Research failed", error.message);

            insightsContainer.innerHTML =
                empty("fa-brain", "Analysis unavailable", "Check the backend terminal.");

            ideasContainer.innerHTML =
                empty("fa-lightbulb", "Ideas unavailable", "Try again after resolving the error.");

        } finally {
            runButton.disabled = false;

            runButton.innerHTML =
                '<i class="fa-solid fa-wand-magic-sparkles"></i> Run Research Agent';
        }
    });

    // ------------------------------------
    // 11. CARD DETAILS BUTTON
    // ------------------------------------

    document.addEventListener("click", event => {
        const button = event.target.closest(".expand-card");

        if (!button) return;

        const full = button.parentElement.querySelector(".full-content");

        if (!full) return;

        full.hidden = !full.hidden;

        button.innerHTML = full.hidden
            ? 'Read details <i class="fa-solid fa-arrow-right"></i>'
            : 'Show less <i class="fa-solid fa-arrow-up"></i>';
    });

    // ------------------------------------
    // 12. VIEW SWITCHING & NAVIGATION
    // ------------------------------------

    function switchView(viewId) {
        const dashboardView = $("dashboardView");
        const conferencesView = $("conferencesView");

        if (!dashboardView || !conferencesView) {
            console.error("Missing dashboardView or conferencesView in index.html");
            return;
        }

        if (viewId === "conferencesView") {
            dashboardView.hidden = true;
            dashboardView.style.display = "none";

            conferencesView.hidden = false;
            conferencesView.style.display = "block";
            window.scrollTo({ top: 0, behavior: "smooth" });
        } else {
            conferencesView.hidden = true;
            conferencesView.style.display = "none";

            dashboardView.hidden = false;
            dashboardView.style.display = "block";
        }

        document.querySelectorAll(".nav-link").forEach(item => {
            const href = item.getAttribute("href") || "";
            const isSectionAnchor = href.startsWith("#") && href.length > 1;
            item.classList.toggle("active", item.dataset.view === viewId && !isSectionAnchor);
        });
    }

    $("refreshConferencesBtn")?.addEventListener("click", loadConferences);

    $("viewAllConferencesBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        switchView("conferencesView");
    });

    $("backToDashboardBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        switchView("dashboardView");
    });

    document.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", (e) => {
            const targetView = link.dataset.view || "dashboardView";
            const href = link.getAttribute("href");

            switchView(targetView);

            document.querySelectorAll(".nav-link")
                .forEach(item => item.classList.remove("active"));
            link.classList.add("active");

            if (!href || href === "#") {
                e.preventDefault();
                window.scrollTo({ top: 0, behavior: "smooth" });
            }
        });
    });

    // Initial startup loading: conferences + latest persisted weekly/daily analysis
    loadConferences();
    loadLatestResearch();
});


