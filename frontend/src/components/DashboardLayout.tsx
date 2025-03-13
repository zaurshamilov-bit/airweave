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
  MessageSquare,
  BookOpen,
  ExternalLink,
  Sun,
  Moon,
  Monitor,
  Check
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useTheme } from "@/lib/theme-provider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { GradientBackground, GradientCard } from "@/components/ui/gradient-background";

const DashboardLayout = () => {
  const location = useLocation();
  const { resolvedTheme, setTheme } = useTheme();

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
    <GradientBackground className="min-h-screen">
      <GradientCard className="h-full">
        <div className="flex h-screen overflow-hidden">
          {/* Mobile Menu Button */}
          <div className="lg:hidden fixed top-4 left-4 z-[30]">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="bg-background-alpha-90">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 bg-background-alpha-90 backdrop-blur-md">
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
          <div className="hidden w-64 lg:block fixed h-screen left-1 top-1 transition-all duration-300 ease-in-out z-20 shadow-sm border-r border-border/30">
            <div className="flex h-14 items-center px-6">
              <Link
                to="/"
                className="flex items-center transition-transform duration-200"
              >
                <img
                  src={logoSrc}
                  alt="Airweave"
                  className="h-8 pr-4"
                />
              </Link>
            </div>
            <nav className="flex flex-col justify-between h-[calc(100%-3.5rem)]">
              <div className="space-y-1 px-3 pt-3">
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

          {/* Main content with scrollable area that includes the header */}
          <div className="w-full lg:pl-64 flex flex-col h-screen">
            <div className="flex-1 overflow-auto">
              {/* Top Navigation Bar - Now inside the scrollable area */}
              <header className="h-16 sticky pr-2">
                <div className="flex justify-end items-center h-full px-4">
                  <nav className="flex items-center space-x-4">
                    {/* Get a demo button */}
                    <a
                      href="https://cal.com/lennert-airweave/quick-chat"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button
                        variant="outline"
                        className="hidden md:flex border-primary/60 border-[1px] text-primary/90 hover:bg-primary/20 hover:text-foreground/65 h-8 px-3 text-sm"
                      >
                        Get a demo
                      </Button>
                    </a>

                    {/* Theme Switcher */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="rounded-md h-8 w-8 bg-background-alpha-40">
                          {resolvedTheme === 'dark' ? (
                            <Moon className="h-4 w-4" />
                          ) : (
                            <Sun className="h-4 w-4" />
                          )}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-32">
                        <DropdownMenuItem
                          onClick={() => setTheme('light')}
                          className="flex items-center justify-between cursor-pointer"
                        >
                          <div className="flex items-center">
                            <Sun className="mr-2 h-4 w-4" />
                            Light
                          </div>
                          {resolvedTheme === 'light' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setTheme('dark')}
                          className="flex items-center justify-between cursor-pointer"
                        >
                          <div className="flex items-center">
                            <Moon className="mr-2 h-4 w-4" />
                            Dark
                          </div>
                          {resolvedTheme === 'dark' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setTheme('system')}
                          className="flex items-center justify-between cursor-pointer"
                        >
                          <div className="flex items-center">
                            <Monitor className="mr-2 h-4 w-4" />
                            System
                          </div>
                          {(resolvedTheme !== 'dark' && resolvedTheme !== 'light') && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </nav>
                </div>
              </header>

              <div className="pb-8 pr-4 h-full">
                  <Outlet />
              </div>
            </div>
          </div>
        </div>
      </GradientCard>
    </GradientBackground>
  );
};

export default DashboardLayout;
