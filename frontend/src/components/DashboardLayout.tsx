import { Link, useLocation, Outlet } from "react-router-dom";
import { 
  LayoutDashboard, 
  RefreshCw, 
  Settings, 
  Database,
  User,
  RefreshCcw,
  Tag,
  Menu,
  MessageSquare
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useTheme } from "@/lib/theme-provider";

const DashboardLayout = () => {
  const location = useLocation();
  const { resolvedTheme } = useTheme();
  
  // Determine which logo to use based on theme
  const logoSrc = resolvedTheme === "dark" ? "/logo-and-lettermark-light.svg" : "/logo-and-lettermark.svg";

  const isRouteActive = (path: string) => {
    if (path === "/white-label") {
      return location.pathname.startsWith("/white-label");
    }
    if (path === "/sync") {
      if (location.pathname === "/sync/create") {
        return false;
      }
      return location.pathname.startsWith("/sync");
    }
    if (path === "/chat") {
      return location.pathname.startsWith("/chat");
    }
    return location.pathname === path;
  };

  const navigation = [
    {
      name: "Set up sync",
      href: "/sync/create",
      icon: RefreshCcw,
      isSpecial: true,
    },
    {
      name: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      name: "Chat playground",
      href: "/chat",
      icon: MessageSquare,
    },
  ];

  const configureNavigation = [
    {
      name: "Synchronizations",
      href: "/sync",
      icon: RefreshCw,
    },
    {
      name: "Sources",
      href: "/sources",
      icon: Database,
    },
    {
      name: "Destinations",
      href: "/destinations",
      icon: Database,
    },
    {
      name: "White Label",
      href: "/white-label",
      icon: Tag,
    }
  ];

  const bottomNavigation = [
    {
      name: "Settings",
      href: "/settings",
      icon: Settings,
    },
    {
      name: "Profile",
      href: "/profile",
      icon: User,
    },
  ];

  const NavLink = ({ item, isActive }: { item: typeof navigation[0], isActive: boolean }) => (
    <Link
      to={item.href}
      className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ease-in-out ${
        isActive
          ? "bg-primary/10 text-primary"
          : item.isSpecial
          ? "bg-gradient-to-r r from-secondary-200/70 to-primary-200/70  text-secondary-900 bg-opacity-60 hover:bg-opacity-90 transform hover:shadow-sm transition-all duration-200 ease-in-out py-2 "
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      }`}
    >
      <item.icon className="mr-3 h-5 w-5" />
      {item.name}
    </Link>
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="flex h-screen">
        {/* Mobile Menu Button */}
        <div className="lg:hidden fixed top-4 left-4 z-[30]">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="bg-background">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <div className="flex h-16 items-center px-6">
                <Link to="/" className="flex items-center">
                  <img 
                    src={logoSrc} 
                    alt="Airweave" 
                    className="h-6 pr-4"
                  />
                </Link>
              </div>
              <nav className="flex flex-col justify-between h-[calc(100%-4rem)]">
                <div className="space-y-1 px-3">
                  {navigation.map((item) => (
                    <NavLink 
                      key={item.name} 
                      item={item} 
                      isActive={isRouteActive(item.href)}
                    />
                  ))}
                  <div className="mt-8">
                    <span className="px-3 text-xs font-semibold text-muted-foreground/70 tracking-wider">
                      CONFIGURE
                    </span>
                    <div className="mt-2">
                      {configureNavigation.map((item) => (
                        <NavLink 
                          key={item.name} 
                          item={item} 
                          isActive={isRouteActive(item.href)}
                        />
                      ))}
                    </div>
                  </div>
                </div>
                <div className="space-y-1 px-3 mb-6">
                  {bottomNavigation.map((item) => (
                    <NavLink 
                      key={item.name} 
                      item={item} 
                      isActive={isRouteActive(item.href)}
                    />
                  ))}
                </div>
              </nav>
            </SheetContent>
          </Sheet>
        </div>

        {/* Desktop Sidebar */}
        <div className="hidden w-64 border-r bg-card lg:block transition-all duration-300 ease-in-out">
          <div className="flex h-16 items-center px-6">
            <Link 
              to="/" 
              className="flex items-center transition-transform duration-200 hover:scale-105"
            >
              <img 
                src={logoSrc} 
                alt="Airweave" 
                className="h-8 pr-4"
              />
            </Link>
          </div>
          <nav className="flex flex-col justify-between h-[calc(100%-4rem)]">
            <div className="space-y-1 px-3">
              {navigation.map((item) => (
                <NavLink 
                  key={item.name} 
                  item={item} 
                  isActive={isRouteActive(item.href)}
                />
              ))}
              <div className="mt-8">
                <span className="px-3 text-xs font-semibold text-muted-foreground/70 tracking-wider">
                  CONFIGURE
                </span>
                <div className="mt-2">
                  {configureNavigation.map((item) => (
                    <NavLink 
                      key={item.name} 
                      item={item} 
                      isActive={isRouteActive(item.href)}
                    />
                  ))}
                </div>
              </div>
            </div>
            <div className="space-y-1 px-3 mb-6">
              {bottomNavigation.map((item) => (
                <NavLink 
                  key={item.name} 
                  item={item} 
                  isActive={isRouteActive(item.href)}
                />
              ))}
            </div>
          </nav>
        </div>

        {/* Main content */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <main className="flex-1 overflow-y-auto pt-16 lg:pt-0">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};

export default DashboardLayout;