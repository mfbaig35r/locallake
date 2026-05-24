export default function Home() {
  return (
    <main style={{ padding: "3rem", maxWidth: 720 }}>
      <h1 style={{ margin: 0, fontSize: "2rem" }}>LocalLake</h1>
      <p style={{ color: "#a3a3a3", marginTop: ".5rem" }}>
        Phase 0 — services are up. The real UI lands in Phase 2.
      </p>
      <ul style={{ marginTop: "2rem", lineHeight: 1.8 }}>
        <li>
          API health:{" "}
          <code style={{ background: "#1a1a1a", padding: "2px 6px" }}>
            http://localhost:8000/health
          </code>
        </li>
        <li>
          Plan:{" "}
          <code style={{ background: "#1a1a1a", padding: "2px 6px" }}>
            PLAN.md
          </code>
        </li>
      </ul>
    </main>
  );
}
