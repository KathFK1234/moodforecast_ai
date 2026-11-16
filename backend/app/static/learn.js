// Learns, in this browser only, which activities this visitor likes, from their 👍 and 👎.
//
// The model is a small contextual bandit with Thompson sampling. Each activity has a
// Beta(likes + 1, dislikes + 1) belief about how much it is liked, kept separately for
// each kind of weather (warm, mild or cold; dry or wet; day or evening). Likes are
// shared, more weakly, with the same activity in other weather and with its family
// (ball games, time on the water, quiet time in...), so a few taps already change the
// picks. Old votes fade with a half-life, so tastes can change, and the evidence for any
// one activity is capped, so nothing ever becomes certain and the picks keep exploring.
//
// It only ever chooses among the activities the server says the rules allow right now
// (`suited`), and the server checks the choice against the same rules again, so learning
// can reorder what is safe and practical but never get past it.
//
// Nothing here is sent anywhere: the votes stay in localStorage under STORAGE_KEY.
// If storage is blocked, learning lasts until the page is closed.
const Learner = (() => {
    const STORAGE_KEY = 'moodforecast:tastes';
    const VERSION = 1;
    const DAY_MS = 24 * 60 * 60 * 1000;
    const HALF_LIFE_DAYS = 45;      // A vote counts half as much after this long
    const MAX_EVIDENCE = 8;         // Votes beyond this many (decayed) are scaled down
    const SAME_ACTIVITY_SHARE = 0.5;  // The same activity in other weather
    const FAMILY_SHARE = 0.35;        // Its family in this weather
    const FAMILY_ELSEWHERE_SHARE = 0.15;  // Its family in other weather
    const EXPLORE = 0.15;           // How often the server's own random pick is used instead
    const FAVOURITE_BOOST = 1.1;    // Local favourites, as the server's random pick also prefers
    const INDOOR_DAMPING = 0.85;    // Indoors, when the weather allows going out
    const MAX_CELLS = 2000;         // Far more than 65 activities x 12 contexts, a guard against odd data

    let memory = null;  // The state, kept here too, so blocked storage still works for a visit

    function empty() {
        return { v: VERSION, a: {}, f: {} };
    }

    function load() {
        if (memory) return memory;
        memory = empty();
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
            if (saved && saved.v === VERSION && isCells(saved.a) && isCells(saved.f)) memory = saved;
        } catch (e) {
            // Storage blocked or unreadable: start afresh
        }
        return memory;
    }

    function isCells(table) {
        return table && typeof table === 'object' && !Array.isArray(table);
    }

    function save() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(memory));
        } catch (e) {
            // Storage blocked or full: learning lasts for this visit
        }
    }

    // The kind of weather a vote was made in, e.g. "mild-dry-day"
    function context(weather) {
        const feels = weather.feels_like_c == null ? weather.temp_c : weather.feels_like_c;
        const temp = feels >= 24 ? 'warm' : feels >= 12 ? 'mild' : 'cold';
        const wet = /rain|drizzle|shower|snow|thunder|storm|sleet/i.test(weather.condition || '') ? 'wet' : 'dry';
        return `${temp}-${wet}-${weather.is_day ? 'day' : 'evening'}`;
    }

    // "mild-dry-day" -> "mild, dry days"
    function describeContext(ctx) {
        const [temp, wet, time] = ctx.split('-');
        return `${temp}, ${wet} ${time === 'day' ? 'days' : 'evenings'}`;
    }

    function decayed(cell, now) {
        if (!Array.isArray(cell) || cell.length !== 3) return [0, 0];
        const [likes, dislikes, at] = cell.map(Number);
        if (![likes, dislikes, at].every(Number.isFinite)) return [0, 0];
        const factor = Math.pow(0.5, Math.max(now - at, 0) / (HALF_LIFE_DAYS * DAY_MS));
        return [Math.max(likes, 0) * factor, Math.max(dislikes, 0) * factor];
    }

    function cellsOf(table, key) {
        const cells = table[key];
        return isCells(cells) ? cells : {};
    }

    function countCells(state) {
        return [state.a, state.f].reduce(
            (total, table) => total + Object.values(table).reduce((sum, cells) => sum + Object.keys(isCells(cells) ? cells : {}).length, 0),
            0
        );
    }

    function add(table, key, ctx, likes, dislikes, now) {
        if (!isCells(table[key])) table[key] = {};
        const [l, d] = decayed(table[key][ctx], now);
        const next = [Math.max(l + likes, 0), Math.max(d + dislikes, 0)];
        if (next[0] < 0.01 && next[1] < 0.01) delete table[key][ctx];
        else table[key][ctx] = [round(next[0]), round(next[1]), now];
        if (!Object.keys(table[key]).length) delete table[key];
    }

    const round = (value) => Math.round(value * 1000) / 1000;

    // Record a vote for a pick: +1 like, -1 dislike, 0 none. `previous` is undone first,
    // so changing one's mind about the same pick doesn't count twice.
    function vote(pick, value, previous = 0, now = Date.now()) {
        const state = load();
        if (countCells(state) > MAX_CELLS) {
            state.a = {};
            state.f = {};
        }
        [[previous, -1], [value, 1]].forEach(([which, sign]) => {
            if (!which) return;
            const likes = which > 0 ? sign : 0;
            const dislikes = which < 0 ? sign : 0;
            add(state.a, pick.name, pick.ctx, likes, dislikes, now);
            if (pick.family) add(state.f, pick.family, pick.ctx, likes, dislikes, now);
        });
        save();
    }

    // Decayed likes and dislikes behind an activity in this weather, shared as described above
    function evidence(name, family, ctx, now = Date.now()) {
        const state = load();
        const own = cellsOf(state.a, name);
        const kin = family ? cellsOf(state.f, family) : {};
        let likes = 0;
        let dislikes = 0;
        const contexts = new Set([...Object.keys(own), ...Object.keys(kin)]);
        contexts.forEach((c) => {
            const [ol, od] = decayed(own[c], now);
            // The family's votes, without this activity's own
            const [fl, fd] = decayed(kin[c], now).map((value, i) => Math.max(value - (i ? od : ol), 0));
            const ownShare = c === ctx ? 1 : SAME_ACTIVITY_SHARE;
            const kinShare = c === ctx ? FAMILY_SHARE : FAMILY_ELSEWHERE_SHARE;
            likes += ownShare * ol + kinShare * fl;
            dislikes += ownShare * od + kinShare * fd;
        });
        const total = likes + dislikes;
        if (total > MAX_EVIDENCE) {
            likes *= MAX_EVIDENCE / total;
            dislikes *= MAX_EVIDENCE / total;
        }
        return { likes, dislikes };
    }

    function hasLearned() {
        const state = load();
        return Object.keys(state.a).length > 0;
    }

    // Gamma(shape, 1) by Marsaglia and Tsang; shape >= 1 here
    function gamma(shape, random) {
        const d = shape - 1 / 3;
        const c = 1 / Math.sqrt(9 * d);
        for (;;) {
            let x;
            let v;
            do {
                x = normal(random);
                v = 1 + c * x;
            } while (v <= 0);
            v = v * v * v;
            const u = random();
            if (u < 1 - 0.0331 * x * x * x * x) return d * v;
            if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
        }
    }

    function normal(random) {
        const u = 1 - random();
        const v = random();
        return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    }

    function beta(a, b, random) {
        const x = gamma(a, random);
        return x / (x + gamma(b, random));
    }

    // A draw of how much this visitor likes each choice, with the server's own leanings
    function score(choice, ctx, outdoorsOpen, random, now) {
        const { likes, dislikes } = evidence(choice.name, choice.family, ctx, now);
        let value = beta(likes + 1, dislikes + 1, random);
        if (choice.favourite) value *= FAVOURITE_BOOST;
        if (outdoorsOpen && choice.group === 'Indoors') value *= INDOOR_DAMPING;
        return value;
    }

    // The activity to ask the server for, or null to let it pick at random.
    // `choices` come from /api/activities/{location}; only `suited` ones are considered.
    function choose(choices, ctx, exclude = '', random = Math.random, now = Date.now()) {
        if (!hasLearned()) return null;
        if (random() < EXPLORE) return null;
        const pool = (choices || []).filter((choice) => choice.suited && choice.name !== exclude);
        if (!pool.length) return null;
        const outdoorsOpen = pool.some((choice) => choice.group !== 'Indoors');
        let best = null;
        let bestScore = -1;
        pool.forEach((choice) => {
            const value = score(choice, ctx, outdoorsOpen, random, now);
            if (value > bestScore) {
                best = choice;
                bestScore = value;
            }
        });
        return best ? best.name : null;
    }

    // Order the quick picks, a menu rather than a pick: liked ones first and disliked ones
    // last, by the expected share of likes; local favourites slightly ahead of the rest, which
    // are shuffled, so there's still something new each visit. null until there are votes.
    function rank(choices, ctx, random = Math.random, now = Date.now()) {
        if (!hasLearned()) return null;
        return (choices || [])
            .map((choice) => {
                const { likes, dislikes } = evidence(choice.name, choice.family, ctx, now);
                const mean = (likes + 1) / (likes + dislikes + 2);
                return { choice, value: mean * (choice.favourite ? FAVOURITE_BOOST : 1), tie: random() };
            })
            .sort((x, y) => y.value - x.value || x.tie - y.tie)
            .map((entry) => entry.choice);
    }

    // One short line on why a learned pick was made, or '' when there's nothing honest to
    // say: it names likes only where they outweigh dislikes
    function reason(choice, ctx, now = Date.now()) {
        const state = load();
        const own = cellsOf(state.a, choice.name);
        const [likedHere, dislikedHere] = decayed(own[ctx], now);
        if (likedHere >= 0.5 && likedHere > dislikedHere) return `You've liked ${choice.name} on ${describeContext(ctx)}.`;
        const [liked, disliked] = Object.values(own).reduce(
            ([l, d], cell) => {
                const [cl, cd] = decayed(cell, now);
                return [l + cl, d + cd];
            },
            [0, 0]
        );
        if (liked >= 0.5 && liked > disliked) return `You've liked ${choice.name} before.`;
        const { likes, dislikes } = evidence(choice.name, choice.family, ctx, now);
        if (choice.family && likes >= 0.3 && likes > dislikes) return `You've liked other ${choice.family}.`;
        return '';
    }

    function forget() {
        memory = empty();
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (e) {
            // Storage blocked: nothing was kept there
        }
    }

    return { context, vote, evidence, hasLearned, choose, rank, reason, forget };
})();
