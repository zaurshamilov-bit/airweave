import { Button } from "@/components/ui/button";
import { ArrowRight, Zap, Database, Link2, Star, GitFork, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";

export const Hero = () => {
  const navigate = useNavigate();

  const handleStartSyncing = () => {
    navigate("/login");
  };

  return (
    <div className="relative overflow-hidden bg-background pt-[6.5rem]">
      <div className="container relative">
        <div className="flex flex-col items-center text-center space-y-8">
          <div className="space-y-6 max-w-3xl">
            <h1 className="text-4xl font-bold sm:text-6xl">
              Meet
              <span className="bg-gradient-to-r from-primary-400 to-secondary-400 bg-clip-text text-transparent">
                {" "}
                Airweave
              </span>
              , Your Data-to-Vector Pipeline
            </h1>
            <p className="mx-auto max-w-[42rem] leading-normal text-muted-foreground sm:text-xl sm:leading-8">
              Transform any workspace data into vector embeddings in <strong>minutes</strong>, not days. Built by agent developers, for agent developers.
            </p>

            <div className="flex items-center justify-center space-x-8">
              <div className="flex items-center space-x-2">
                <Star className="h-5 w-5 text-yellow-400 fill-yellow-400" />
                <span className="text-lg font-semibold">1.2k stars</span>
              </div>
              <div className="flex items-center space-x-2">
                <GitFork className="h-5 w-5 text-muted-foreground" />
                <span className="text-lg font-semibold">180 forks</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="flex -space-x-2">
                  <img className="h-8 w-8 rounded-full border-2 border-background" src="https://github.com/shadcn.png" alt="Contributor" />
                  <img className="h-8 w-8 rounded-full border-2 border-background" src="https://github.com/theodorusclarence.png" alt="Contributor" />
                  <img className="h-8 w-8 rounded-full border-2 border-background" src="https://github.com/delba.png" alt="Contributor" />
                </div>
                <span className="text-lg font-semibold">45 contributors</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap justify-center gap-4">
            <Button size="lg" className="h-12 px-8" onClick={handleStartSyncing}>
              Start Syncing
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline" className="h-12 px-8">
              Watch Demo
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-16 w-full max-w-5xl">
            <div className="flex flex-col items-center space-y-4 p-6 rounded-lg border bg-card text-card-foreground shadow-sm">
              <div className="p-3 rounded-full bg-primary-100">
                <Zap className="h-6 w-6 text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold">3-Click Setup</h3>
              <p className="text-muted-foreground text-center">
                Connect your workspace, select your data, and choose your vector DB. That's it!
              </p>
            </div>

            <div className="flex flex-col items-center space-y-4 p-6 rounded-lg border bg-card text-card-foreground shadow-sm">
              <div className="p-3 rounded-full bg-primary-100">
                <Link2 className="h-6 w-6 text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold">White Label</h3>
              <p className="text-muted-foreground text-center">
                Handle OAuth integration with your users' workspaces to vectorize their information.
              </p>
            </div>

            <div className="flex flex-col items-center space-y-4 p-6 rounded-lg border bg-card text-card-foreground shadow-sm">
              <div className="p-3 rounded-full bg-primary-100">
                <RefreshCw className="h-6 w-6 text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold">Always in Sync</h3>
              <p className="text-muted-foreground text-center">
                Changes in your workspace are automatically reflected in your vector database.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};