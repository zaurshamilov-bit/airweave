import { Link, useLocation, Outlet, useNavigate } from "react-router-dom";
import {
  Settings,
  Menu,
  Sun,
  Moon,
  Monitor,
  Check,
  Plus,
  Key,
  Tag,
  ChevronDown,
  ChevronRight,
  Box,
  ExternalLink,
  LayoutGrid,
  Home
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useTheme } from "@/lib/theme-provider";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { GradientBackground, GradientCard } from "@/components/ui/gradient-background";
import { DiscordIcon } from "@/components/ui/discord-icon";
import { cn } from "@/lib/utils";
import { UserProfileDropdown } from "@/components/UserProfileDropdown";
import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { onCollectionEvent, COLLECTION_DELETED, COLLECTION_CREATED, COLLECTION_UPDATED } from "@/lib/events";

// Interface for Collection type
interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

const DashboardLayout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { resolvedTheme, setTheme } = useTheme();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isLoadingCollections, setIsLoadingCollections] = useState(false);
  const [collectionError, setCollectionError] = useState<string | null>(null);
  const [collectionsOpen, setCollectionsOpen] = useState(true);

  // Determine which logo to use based on theme
  const logoSrc = resolvedTheme === "dark" ? "/logo-and-lettermark-light.svg" : "/logo-and-lettermark.svg";

  // Add array of routes that should be non-scrollable
  const nonScrollableRoutes = ['/chat', '/chat/'];

  // Check if current route should be non-scrollable
  const isNonScrollable = nonScrollableRoutes.some(route =>
    location.pathname === route || location.pathname.startsWith('/chat/'));

  // Function to fetch collections from the API
  const fetchCollections = useCallback(async () => {
    setIsLoadingCollections(true);
    setCollectionError(null);

    try {
      const response = await apiClient.get('/collections');

      if (response.ok) {
        const data = await response.json();
        setCollections(data);
      } else {
        const errorText = await response.text();
        setCollectionError(`Failed to load collections: ${errorText}`);
      }
    } catch (err) {
      setCollectionError(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsLoadingCollections(false);
    }
  }, []);

  // Initial fetch of collections
  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  // Listen for collection events to refresh the list
  useEffect(() => {
    // Subscribe to collection events
    const unsubscribeDeleted = onCollectionEvent(COLLECTION_DELETED, () => {
      fetchCollections();
    });

    const unsubscribeCreated = onCollectionEvent(COLLECTION_CREATED, () => {
      fetchCollections();
    });

    const unsubscribeUpdated = onCollectionEvent(COLLECTION_UPDATED, () => {
      fetchCollections();
    });

    // Cleanup event listeners
    return () => {
      unsubscribeDeleted();
      unsubscribeCreated();
      unsubscribeUpdated();
    };
  }, [fetchCollections]);

  const handleCreateCollection = () => {
    navigate('/collections/create');
  };

  // Active status for nav items
  const isActive = (path: string) => {
    if (path.startsWith('/collections/')) {
      return location.pathname === path;
    }
    if (path === '/white-label') {
      return location.pathname.startsWith('/white-label');
    }
    if (path === '/settings/api-keys') {
      return location.pathname === '/settings/api-keys';
    }
    if (path === '/settings') {
      return location.pathname === '/settings';
    }
    return false;
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <div className="flex h-14 items-center px-4 mb-2">
        <Link to="/" className="flex items-center">
          <img src={logoSrc} alt="Airweave" className="h-8" />
        </Link>
      </div>

      <ScrollArea className="flex-1 px-3 py-1">
        <div className="space-y-6">
          {/* Create Collection Button */}
          <div className="pb-2 pt-1 px-2">
            <Button
              onClick={handleCreateCollection}
              variant="outline"
              size="sm"
              className="flex items-center justify-start pl-6 w-full gap-1.5 text-sm text-primary hover:bg-primary/10 bg-background border border-primary/60 hover:text-primary rounded-md py-1.5 font-medium transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Create collection
            </Button>
          </div>

          {/* Home Button */}
          <div className="pb-2 px-2">
            <Link
              to="/"
              className={cn(
                "flex items-center px-2 py-1.5 text-sm rounded-md relative transition-colors",
                location.pathname === "/" || location.pathname === "/dashboard"
                  ? "text-primary font-medium bg-primary/5"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
              )}
            >
              {(location.pathname === "/" || location.pathname === "/dashboard") && (
                <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-primary rounded-r-sm" />
              )}
              <Home className="mr-2 h-4 w-4 opacity-70" />
              Dashboard
            </Link>
          </div>

          {/* Collections Section */}
          <Collapsible
            open={collectionsOpen}
            onOpenChange={setCollectionsOpen}
            className="space-y-1"
          >
            <CollapsibleTrigger className="flex items-center justify-between w-full px-2 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              <span className="font-semibold">Collections</span>
              {collectionsOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-1">
              <div className="ml-1 pl-1 border-l border-border/50 space-y-0.5">
                {isLoadingCollections ? (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">Loading...</div>
                ) : collectionError ? (
                  <div className="px-2 py-1.5 text-xs text-destructive">{collectionError}</div>
                ) : collections.length === 0 ? (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">No collections</div>
                ) : (
                  <>
                    {/* Display maximum 20 collections */}
                    {collections.slice(0, 20).map((collection) => (
                      <Link
                        key={collection.id}
                        to={`/collections/${collection.readable_id}`}
                        className={cn(
                          "flex items-center px-2 py-1.5 text-sm rounded-md relative transition-colors",
                          isActive(`/collections/${collection.readable_id}`)
                            ? "text-primary font-medium bg-primary/5"
                            : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
                        )}
                      >
                        {isActive(`/collections/${collection.readable_id}`) && (
                          <div className="absolute left-[-2px] top-0 bottom-0 w-[2px] bg-primary rounded-r-sm" />
                        )}
                        <LayoutGrid className="mr-2 h-3.5 w-3.5 opacity-70" />
                        <span className="truncate">{collection.name}</span>
                      </Link>
                    ))}

                    {/* Show "See more" link if there are more than 20 collections */}
                    {collections.length > 20 && (
                      <Link
                        to="/collections"
                        className="flex items-center px-2 py-1.5 text-sm rounded-md text-primary hover:text-primary/80 hover:bg-accent/30 mt-1"
                      >
                        <ExternalLink className="mr-2 h-3.5 w-3.5 opacity-70" />
                        <span>See all ({collections.length})</span>
                      </Link>
                    )}
                  </>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* API Keys Section */}
          <div className="space-y-1">
            <h3 className="font-semibold px-2 py-1.5 text-sm text-muted-foreground">API keys</h3>
            <Link
              to="/settings/api-keys"
              className={cn(
                "flex items-center px-2 py-1.5 text-sm rounded-md relative transition-colors",
                isActive('/settings/api-keys')
                  ? "text-primary font-medium bg-primary/5"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
              )}
            >
              {isActive('/settings/api-keys') && (
                <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-primary rounded-r-sm" />
              )}
              <Key className="mr-2 h-4 w-4 opacity-70" />
              API keys
            </Link>
          </div>

          {/* Configure Section */}
          <div className="space-y-1">
            <h3 className="font-semibold px-2 py-1.5 text-sm text-muted-foreground">Configure</h3>
            <div className="space-y-0.5">
              <Link
                to="/white-label"
                className={cn(
                  "flex items-center px-2 py-1.5 text-sm rounded-md relative transition-colors",
                  isActive('/white-label')
                    ? "text-primary font-medium bg-primary/5"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
                )}
              >
                {isActive('/white-label') && (
                  <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-primary rounded-r-sm" />
                )}
                <Tag className="mr-2 h-4 w-4 opacity-70" />
                White Label
              </Link>
              <Link
                to="/settings"
                className={cn(
                  "flex items-center px-2 py-1.5 text-sm rounded-md relative transition-colors",
                  isActive('/settings')
                    ? "text-primary font-medium bg-primary/5"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
                )}
              >
                {isActive('/settings') && (
                  <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-primary rounded-r-sm" />
                )}
                <Settings className="mr-2 h-4 w-4 opacity-70" />
                Settings
              </Link>
            </div>
          </div>
        </div>
      </ScrollArea>

      {/* User Profile Section */}
      <div className="mt-auto pt-2 pb-4 px-3 border-t border-border/30">
        <UserProfileDropdown />
      </div>
    </div>
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
                <SidebarContent />
              </SheetContent>
            </Sheet>
          </div>

          {/* Desktop Sidebar */}
          <div className="hidden w-[240px] lg:block fixed h-screen transition-all duration-300 ease-in-out z-20 border-r border-border/40 bg-background/95">
            <SidebarContent />
          </div>

          {/* Main content with conditionally scrollable area */}
          <div className="w-full lg:pl-[240px] flex flex-col h-screen">
            <div className={cn(
              "flex-1",
              isNonScrollable ? "overflow-hidden" : "overflow-auto"
            )}>
              {/* Top Navigation Bar - Now inside the scrollable area */}
              <header className={`h-16 sticky top-0 pr-2 backdrop-blur-sm z-10 ${resolvedTheme === 'dark' ? 'bg-background/80' : 'bg-background/95'} border-b border-border/30`}>
                <div className="flex justify-end items-center h-full px-6">
                  <nav className="flex items-center space-x-4">
                    {/* Discord icon */}
                    <a
                      href="https://discord.com/invite/484HY9Ehxt"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center hover:bg-background-alpha-40 h-8 w-8 rounded-md"
                    >
                      <DiscordIcon size={20} />
                    </a>

                    {/* Get a demo button */}
                    <a
                      href="https://cal.com/lennert-airweave/airweave-q-a-demo"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button
                        variant="outline"
                        className="hidden md:flex border-primary/60 border-[1px] text-primary/90 hover:bg-primary/10 hover:text-foreground/65 h-8 px-3 text-sm"
                      >
                        Get a demo
                      </Button>
                    </a>

                    {/* Theme Switcher */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="rounded-md h-8 w-8 hover:bg-background-alpha-40 text-muted-foreground">
                          {resolvedTheme === 'dark' ? (
                            <Moon className="h-[18px] w-[18px]" />
                          ) : (
                            <Sun className="h-[18px] w-[18px]" />
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

              <div className={cn(
                "h-[calc(100%-4rem)]",
                isNonScrollable ? "overflow-hidden" : "pb-8"
              )}>
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
