export default function GalaxyLogo({ size = 36, className = '' }) {
  return (
    <div
      className={`group relative flex items-center justify-center shrink-0 rounded-2xl p-1 transition-all duration-300 hover:scale-105 ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Outer ambient cosmic nebula aura */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-cyan-500/30 via-fuchsia-500/25 to-violet-600/35 blur-md opacity-80 group-hover:opacity-100 transition-opacity" />

      {/* Galaxy SVG Icon */}
      <svg
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="relative z-10 w-full h-full drop-shadow-[0_0_12px_rgba(56,189,248,0.5)]"
      >
        <defs>
          <radialGradient id="logoSpaceGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
            <stop offset="35%" stopColor="#a855f7" stopOpacity="0.8" />
            <stop offset="70%" stopColor="#6366f1" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#050716" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="logoSpiral1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="50%" stopColor="#818cf8" />
            <stop offset="100%" stopColor="#c084fc" />
          </linearGradient>
          <linearGradient id="logoSpiral2" x1="100%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#f43f5e" />
            <stop offset="50%" stopColor="#a855f7" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
          <linearGradient id="logoCore" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#e0f2fe" />
          </linearGradient>
        </defs>

        {/* Space Backdrop */}
        <circle cx="32" cy="32" r="30" fill="#060814" />
        <circle cx="32" cy="32" r="30" fill="url(#logoSpaceGlow)" />
        <circle cx="32" cy="32" r="29.5" stroke="#38bdf8" strokeOpacity="0.3" strokeWidth="1" />

        {/* Outer Orbit Rings */}
        <ellipse
          cx="32"
          cy="32"
          rx="24"
          ry="12"
          transform="rotate(-30 32 32)"
          stroke="url(#logoSpiral1)"
          strokeWidth="2.2"
          strokeDasharray="32 10"
          strokeLinecap="round"
          opacity="0.9"
        />
        <ellipse
          cx="32"
          cy="32"
          rx="20"
          ry="9"
          transform="rotate(35 32 32)"
          stroke="url(#logoSpiral2)"
          strokeWidth="2"
          strokeDasharray="24 8"
          strokeLinecap="round"
          opacity="0.9"
        />

        {/* Inner Vortex Arms */}
        <path
          d="M 32 18 C 39 18 45 23 44 31 C 43 38 35 43 27 40 C 21 38 19 31 23 26 C 26 22 31 23 33 27 C 34 30 32 33 29 32"
          stroke="url(#logoSpiral1)"
          strokeWidth="2.4"
          strokeLinecap="round"
          fill="none"
          opacity="0.95"
        />
        <path
          d="M 32 46 C 25 46 19 41 20 33 C 21 26 29 21 37 24 C 43 26 45 33 41 38 C 38 42 33 41 31 37 C 30 34 32 31 35 32"
          stroke="url(#logoSpiral2)"
          strokeWidth="2.1"
          strokeLinecap="round"
          fill="none"
          opacity="0.8"
        />

        {/* Orbiting Stardust Nodes */}
        <circle cx="16" cy="22" r="1.6" fill="#38bdf8" />
        <circle cx="48" cy="42" r="1.6" fill="#f43f5e" />
        <circle cx="45" cy="19" r="1.3" fill="#c084fc" />
        <circle cx="19" cy="45" r="1.3" fill="#06b6d4" />
        <circle cx="28" cy="14" r="1.1" fill="#ffffff" />
        <circle cx="36" cy="50" r="1.1" fill="#ffffff" />

        {/* Radiant Star Flare Core */}
        <circle cx="32" cy="32" r="4.5" fill="#ffffff" />
        <path
          d="M 32 20 Q 32 32 20 32 Q 32 32 32 44 Q 32 32 44 32 Q 32 32 32 20 Z"
          fill="url(#logoCore)"
        />
        <circle cx="32" cy="32" r="1.8" fill="#ffffff" />
      </svg>
    </div>
  )
}
