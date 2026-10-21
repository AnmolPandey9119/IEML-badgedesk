/* ==========================================================
   badge-download.css
   Extra pieces the e-badge page needs on top of the shared
   .shell/.identity/.card/.btn system in css/style.css.
   Same Mart Days poster theme: cream, rust-brown, forest green
   and gold. Class names unchanged — only the look is new.
   ========================================================== */

   .badge-hero-icon {
    width: 64px;
    height: 64px;
    margin: 4px auto 16px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--rust) 0%, var(--rust-dark) 100%);
    color: #fff;
    box-shadow: 0 0 0 4px var(--gold-soft), 0 12px 24px rgba(124, 45, 20, 0.3);
  }
  
  .badge-hero-icon svg { width: 30px; height: 30px; }
  
  #lookup-section h2,
  #lookup-section .hint {
    text-align: center;
  }
  
  #lookup-section .hint { margin-bottom: 4px; }
  
  /* ---------------- Button spinner ---------------- */
  
  .btn-primary {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }
  
  .btn-label { font-size: 1.15rem; }
  
  .btn-spinner {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 3px solid rgba(255, 255, 255, 0.35);
    border-top-color: var(--gold-bright);
    animation: badge-spin 0.7s linear infinite;
  }
  
  @keyframes badge-spin {
    to { transform: rotate(360deg); }
  }
  
  .btn[disabled] { opacity: 0.8; cursor: not-allowed; }
  
  /* the » arrow suits "Find & Download" only; Share button keeps its icon */
  #download-again-btn::after { display: none; }
  
  /* ---------------- Secondary "link" button ---------------- */
  
  .btn-link {
    background: transparent;
    box-shadow: none;
    color: var(--rust);
    margin-top: 12px;
    font-family: var(--sans);
    font-size: 0.88rem;
    font-weight: 600;
    letter-spacing: 0;
    text-transform: none;
    text-decoration: underline;
    text-underline-offset: 3px;
    transition: color 0.15s;
  }
  
  .btn-link:hover { color: var(--rust-dark); }
  .btn-link:focus-visible { outline: 3px solid var(--gold-soft); outline-offset: 3px; border-radius: 6px; }
  
  /* ---------------- Success header ---------------- */
  
  .success-icon {
    width: 68px;
    height: 68px;
    margin: 4px auto 14px;
    color: #fff;
    font-size: 0;
  }
  /* this page draws its tick with an inline SVG, so hide the CSS tick */
  .success-icon::before { display: none; }
  .success-icon svg { width: 32px; height: 32px; }
  
  .success-sub {
    color: var(--ink-muted);
    font-size: 0.88rem;
    line-height: 1.5;
    max-width: 38ch;
    margin: 0 auto 4px;
  }
  
  /* ---------------- Badge "ticket" wrapper ---------------- */
  /* Boarding-pass feel: tri-colour edge + perforated notches. */
  
  .badge-ticket {
    position: relative;
    margin: 24px auto 20px;
    max-width: 350px;
    border-radius: 20px;
    padding: 3px;
    background: linear-gradient(135deg, var(--gold-bright) 0%, var(--rust) 50%, var(--green) 100%);
    box-shadow: 0 16px 34px rgba(90, 31, 13, 0.22), 0 2px 8px rgba(90, 31, 13, 0.12);
    animation: badge-rise 0.5s ease-out both;
    animation-delay: 0.1s;
  }
  
  @keyframes badge-rise {
    0% { transform: translateY(10px); opacity: 0; }
    100% { transform: translateY(0); opacity: 1; }
  }
  
  .badge-ticket-notch {
    position: absolute;
    top: 50%;
    width: 22px;
    height: 22px;
    background: var(--card-bg);
    border-radius: 50%;
    transform: translateY(-50%);
    z-index: 2;
  }
  
  .badge-ticket-notch-left { left: -11px; }
  .badge-ticket-notch-right { right: -11px; }
  
  /* ---------------- Badge preview ---------------- */
  
  .badge-confirm {
    margin: 0;
    padding: 32px 20px 26px;
    border-radius: 17px;
    background:
      radial-gradient(120% 140% at 50% -10%, rgba(228, 168, 46, 0.22) 0%, transparent 55%),
      linear-gradient(180deg, #fffaf0 0%, var(--sand) 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  
  .badge-confirm-icon {
    width: 68px;
    height: 68px;
    margin-bottom: 16px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(150deg, #266443 0%, var(--green-dark) 100%);
    box-shadow: 0 0 0 4px var(--gold-soft), 0 12px 22px rgba(20, 55, 35, 0.3);
    animation: pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    animation-delay: 0.15s;
  }
  
  .badge-confirm-icon svg { width: 36px; height: 36px; }
  
  .badge-confirm-title {
    margin: 0 0 10px;
    font-family: var(--display);
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--brown);
  }
  
  .badge-confirm-file {
    margin: 0;
    max-width: 100%;
    padding: 6px 14px;
    border-radius: 999px;
    background: #fff;
    border: 1px dashed var(--gold);
    font-size: 0.78rem;
    color: var(--brown-soft);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  /* ---------------- Share button icon + iOS hint ---------------- */
  
  .btn-icon {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }
  
  .ios-hint {
    margin: 14px 0 0;
    text-align: center;
    font-size: 0.78rem;
    line-height: 1.55;
    color: var(--ink-muted);
  }
  
  .ios-hint strong { color: var(--rust); }
  
  @media (max-width: 480px) {
    .badge-confirm { padding: 26px 16px 22px; }
    .badge-ticket { max-width: 100%; }
  }