"use client";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  return <main className="system-page" role="alert">
    <div className="system-page-mark">!</div>
    <p className="system-page-code">System status / Recovery required</p>
    <h1>The command view needs a fresh start.</h1>
    <p>Vidyut could not complete that view. Retry the operation to restore the latest available workspace.</p>
    <button type="button" onClick={reset}>Retry workspace <span>↻</span></button>
    {error.digest && <small className="system-page-reference">Reference: {error.digest}</small>}
  </main>;
}
