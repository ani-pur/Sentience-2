require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });
const express = require("express");
const session = require("express-session");
const initSqlJs = require("sql.js");
const bcrypt = require("bcryptjs");
const path = require("path");
const fs = require("fs");
const cors = require("cors");
const { connect: connectMongo, getDb } = require("./DB/mongo");

const app = express();
const PORT = process.env.PORT || 3000;

// ── Simple logger ──────────────────────────────────────────
function log(tag, msg, data) {
  const ts = new Date().toISOString();
  const extra = data ? " | " + JSON.stringify(data) : "";
  console.log(`[${ts}] [${tag}]  ${msg}${extra}`);
}

// ── Middleware ──────────────────────────────────────────────
app.use(cors({
  origin: "http://localhost:5173",
  credentials: true,
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use(
  session({
    secret: process.env.SESSION_SECRET || "sentience-dev-secret-change-me",
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: 1000 * 60 * 60 * 24, sameSite: "lax" }, // 1 day
  })
);

// Request logger middleware
app.use((req, res, next) => {
  log("REQ", `${req.method} ${req.url}`, {
    session: req.session?.user?.username || "anonymous",
  });
  next();
});

// ── SQLite Setup (sql.js) ──────────────────────────────────
const dbDir = path.join(__dirname, "DB");
const dbPath = path.join(dbDir, "sentience.db");
let db; // will be set after async init

async function initDB() {
  const SQL = await initSqlJs();

  if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

  // Load existing DB file or create a new one
  if (fs.existsSync(dbPath)) {
    const fileBuffer = fs.readFileSync(dbPath);
    db = new SQL.Database(fileBuffer);
    log("DB", "Loaded existing database", { path: dbPath });
  } else {
    db = new SQL.Database();
    log("DB", "Created new database", { path: dbPath });
  }

  db.run(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      pwhash TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL
    )
  `);
  log("DB", "Users table ready");

  // Log existing user count
  const countStmt = db.prepare("SELECT COUNT(*) as cnt FROM users");
  countStmt.step();
  const { cnt } = countStmt.getAsObject();
  countStmt.free();
  log("DB", `Current user count: ${cnt}`);

  saveDB();
}

function saveDB() {
  const data = db.export();
  const buffer = Buffer.from(data);
  fs.writeFileSync(dbPath, buffer);
  log("DB", "Database saved to disk");
}

// ── Helper: serve an HTML file from views ──────────────────
const viewsPath = path.join(__dirname, "views");

function sendPage(res, filename) {
  log("PAGE", `Serving ${filename}`);
  res.sendFile(path.join(viewsPath, filename));
}

// ── Auth middleware (for protected routes) ──────────────────
function requireAuth(req, res, next) {
  if (req.session && req.session.user) return next();
  log("AUTH", "Unauthorized access attempt, redirecting to /");
  return res.redirect("/");
}

// ── Public Routes ──────────────────────────────────────────

// Landing page
app.get("/", (req, res) => {
  sendPage(res, "landingPage.html");
});

// Login page
app.get("/login", (req, res) => {
  if (req.session && req.session.user) {
    log("AUTH", "Already logged in, redirecting to dashboard", { user: req.session.user.username });
    return res.redirect("/dashboard");
  }
  sendPage(res, "login.html");
});

// Signup page
app.get("/signup", (req, res) => {
  if (req.session && req.session.user) {
    log("AUTH", "Already logged in, redirecting to dashboard", { user: req.session.user.username });
    return res.redirect("/dashboard");
  }
  sendPage(res, "sign_up.html");
});

// ── Auth Endpoints ─────────────────────────────────────────

// POST /login – query by username, compare hash, create session
app.post("/login", (req, res) => {
  const { username, password } = req.body;
  log("AUTH", "Login attempt", { username });

  if (!username || !password) {
    log("AUTH", "Login failed: missing fields");
    return res.status(400).send("Username and password are required.");
  }

  const stmt = db.prepare("SELECT * FROM users WHERE username = ?");
  stmt.bind([username]);

  if (!stmt.step()) {
    stmt.free();
    log("AUTH", "Login failed: user not found", { username });
    return res.status(401).send("Invalid username or password.");
  }

  const row = stmt.getAsObject();
  stmt.free();
  log("DB", "User found in database", { id: row.id, username: row.username, email: row.email });

  const match = bcrypt.compareSync(password, row.pwhash);
  if (!match) {
    log("AUTH", "Login failed: password mismatch", { username });
    return res.status(401).send("Invalid username or password.");
  }

  // Hash matches → create session and redirect to React app
  req.session.user = { id: row.id, username: row.username, email: row.email };
  log("AUTH", "Login successful, session created", { id: row.id, username: row.username });
  // Redirect back to the referring origin (works through Vite proxy or directly)
  const origin = req.headers.referer ? new URL(req.headers.referer).origin : "http://localhost:5173";
  return res.redirect(origin);
});

// POST /signup – create new user
app.post("/signup", (req, res) => {
  const { username, email, password, confirm_password } = req.body;
  log("AUTH", "Signup attempt", { username, email });

  if (!username || !email || !password) {
    log("AUTH", "Signup failed: missing fields");
    return res.status(400).send("All fields are required.");
  }
  if (password !== confirm_password) {
    log("AUTH", "Signup failed: password mismatch");
    return res.status(400).send("Passwords do not match.");
  }

  // Check if user already exists
  const checkStmt = db.prepare(
    "SELECT id FROM users WHERE username = ? OR email = ?"
  );
  checkStmt.bind([username, email]);
  if (checkStmt.step()) {
    checkStmt.free();
    log("AUTH", "Signup failed: user already exists", { username, email });
    return res.status(409).send("Username or email already taken.");
  }
  checkStmt.free();

  const pwhash = bcrypt.hashSync(password, 10);
  db.run("INSERT INTO users (username, pwhash, email) VALUES (?, ?, ?)", [
    username,
    pwhash,
    email,
  ]);
  log("DB", "New user inserted", { username, email });
  saveDB();

  // Auto-login after signup
  const newStmt = db.prepare("SELECT * FROM users WHERE username = ?");
  newStmt.bind([username]);
  newStmt.step();
  const newUser = newStmt.getAsObject();
  newStmt.free();

  req.session.user = {
    id: newUser.id,
    username: newUser.username,
    email: newUser.email,
  };
  log("AUTH", "Signup successful, session created", { id: newUser.id, username: newUser.username });
  const origin = req.headers.referer ? new URL(req.headers.referer).origin : "http://localhost:5173";
  return res.redirect(origin);
});

// ── Logout ─────────────────────────────────────────────────
app.get("/logout", (req, res) => {
  const user = req.session?.user?.username || "unknown";
  req.session.destroy(() => {
    log("AUTH", "User logged out, session destroyed", { username: user });
    res.redirect("/");
  });
});

// ── Protected Routes ───────────────────────────────────────

// Dashboard — redirect to React app
app.get("/dashboard", requireAuth, (req, res) => {
  log("AUTH", "Dashboard access granted, redirecting to React app", { user: req.session.user.username });
  return res.redirect("http://localhost:5173");
});

// ── Session check (for React SPA) ────────────────────────
app.get("/api/me", (req, res) => {
  if (req.session && req.session.user) {
    return res.json(req.session.user);
  }
  return res.status(401).json({ error: "Not authenticated" });
});

// ── Sentiment API (MongoDB) ──────────────────────────────────

app.get("/api/sentiment", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brand = req.query.brand;
  const data = await db.collection("sentiment_graph")
                       .find({ brand })
                       .sort({ date: 1 })
                       .toArray();
  res.json(data);
});

app.get("/api/brands", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brands = await db.collection("sentiment_graph").distinct("brand");
  res.json(brands);
});

app.get("/api/posts", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brand = req.query.brand;
  const posts = await db.collection(brand)
                        .find({ type: "post" })
                        .sort({ created_utc: 1 })
                        .toArray();
  res.json(posts);
});

app.get("/api/daily", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brand = req.query.brand;
  const data = await db.collection("daily_sentiment")
                       .find({ brand })
                       .sort({ date: 1 })
                       .toArray();
  res.json(data);
});

// ── Anomalies API ───────────────────────────────────────────
app.get("/api/anomalies", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brand = req.query.brand;
  const query = brand ? { brand } : {};
  const data = await db.collection("anomalies")
                       .find(query)
                       .sort({ date: -1 })
                       .toArray();
  res.json(data);
});

// ── Stock Correlations API ─────────────────────────────────
app.get("/api/correlations", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brand = req.query.brand;
  const query = brand ? { brand } : {};
  const data = await db.collection("correlations")
                       .find(query)
                       .toArray();
  res.json(data);
});

// ── SMS Scores API ─────────────────────────────────────────
app.get("/api/sms", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brand = req.query.brand;
  const query = brand ? { brand } : {};
  const data = await db.collection("sms_scores")
                       .find(query)
                       .sort({ date: 1 })
                       .toArray();
  res.json(data);
});

// ── Alerts API ─────────────────────────────────────────────
app.get("/api/alerts", async (req, res) => {
  const db = getDb();
  if (!db) return res.status(503).json({ error: "MongoDB not connected" });
  const brand = req.query.brand;
  const query = brand ? { brand } : {};
  const data = await db.collection("alerts")
                       .find(query)
                       .sort({ date: -1 })
                       .toArray();
  res.json(data);
});

// ── Interdependency Network API ────────────────────────────
app.get("/api/network", async (req, res) => {
  const network = {
    nodes: [
      { id: "openai", type: "ai", label: "OpenAI" },
      { id: "anthropic", type: "ai", label: "Anthropic" },
      { id: "google", type: "ai", label: "Google" },
      { id: "xai", type: "ai", label: "xAI" },
      { id: "deepseek", type: "ai", label: "DeepSeek" },
      { id: "microsoft", type: "ai", label: "Microsoft" },
      { id: "alibaba", type: "ai", label: "Alibaba" },
      { id: "NVDA", type: "hardware", label: "NVIDIA" },
      { id: "AMD", type: "hardware", label: "AMD" },
      { id: "AMZN", type: "hardware", label: "Amazon" },
      { id: "AVGO", type: "hardware", label: "Broadcom" },
      { id: "INTC", type: "hardware", label: "Intel" },
      { id: "TSM", type: "hardware", label: "TSMC" },
      { id: "MSFT", type: "hardware", label: "Microsoft (Azure)" },
      { id: "005930.KS", type: "hardware", label: "Samsung" },
    ],
    edges: [
      { source: "openai", target: "NVDA" },
      { source: "openai", target: "MSFT" },
      { source: "anthropic", target: "NVDA" },
      { source: "anthropic", target: "AMD" },
      { source: "anthropic", target: "AMZN" },
      { source: "google", target: "NVDA" },
      { source: "google", target: "AMD" },
      { source: "google", target: "AVGO" },
      { source: "google", target: "005930.KS" },
      { source: "google", target: "TSM" },
      { source: "xai", target: "NVDA" },
      { source: "deepseek", target: "NVDA" },
      { source: "deepseek", target: "AMD" },
      { source: "microsoft", target: "NVDA" },
      { source: "microsoft", target: "AMD" },
      { source: "microsoft", target: "INTC" },
      { source: "alibaba", target: "NVDA" },
      { source: "alibaba", target: "TSM" },
    ],
  };
  res.json(network);
});

// ── Catchall: anything else → check session ────────────────
app.get("/{*path}", (req, res) => {
  if (req.session && req.session.user) {
    log("ROUTE", "Catchall: authenticated user, redirecting to React app");
    return res.redirect("http://localhost:5173");
  }
  log("ROUTE", "Catchall: unauthenticated, redirecting to landing");
  return res.redirect("/");
});

// ── Start ──────────────────────────────────────────────────
initDB().then(async () => {
  try {
    await connectMongo();
    log("MONGO", "MongoDB connected");
  } catch (err) {
    log("MONGO", "MongoDB unavailable — API endpoints will fail", { error: err.message });
  }

  app.listen(PORT, "0.0.0.0", () => {
    log("SERVER", `Sentience server running on http://0.0.0.0:${PORT}`);
    log("SERVER", `Local network: have friends connect to http://<your-ip>:${PORT}`);
  });
});
