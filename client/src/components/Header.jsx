import BrandSelector from "./BrandSelector";

export default function Header({ user, brands, selected, onSelect }) {
  return (
    <header className="sticky top-0 z-50 border-b border-primary/10 bg-[#101f22]/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-6">
        {/* Logo */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="text-primary">
            <svg className="w-7 h-7" fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
              <path d="M44 4H30.6666V17.3334H17.3334V30.6666H4V44H44V4Z" fill="currentColor" />
            </svg>
          </div>
          <h1 className="text-lg font-bold tracking-tight">Sentience</h1>
        </div>

        {/* Brand Selector */}
        <div className="flex-1 flex justify-center">
          <BrandSelector brands={brands} selected={selected} onSelect={onSelect} />
        </div>

        {/* User */}
        <div className="flex items-center gap-4 shrink-0">
          {user && (
            <>
              <span className="text-sm text-slate-400">{user.username}</span>
              <a
                href="http://localhost:3000/logout"
                className="text-xs text-slate-500 hover:text-primary transition-colors"
              >
                Logout
              </a>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
