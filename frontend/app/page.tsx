export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-6 text-zinc-100">
      <div className="mx-auto max-w-xl text-center">
        <p className="text-sm tracking-[0.2em] text-zinc-500 uppercase">
          Phase 1 · Project setup
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
          ScreamerScreener
        </h1>
        <p className="mt-4 text-lg text-zinc-400">
          Vortex Bands stock screening. Dashboard arrives in Phase 13 after data,
          math, and triggers are validated.
        </p>
        <p className="mt-8 text-sm text-zinc-500">
          Backend health:{" "}
          <code className="rounded bg-zinc-900 px-2 py-1 text-zinc-300">
            GET /api/health
          </code>
        </p>
      </div>
    </main>
  );
}
