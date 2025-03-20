import React, { createContext, useContext, useState, ReactNode } from 'react';

type ScrollContextType = {
  isScrollable: boolean;
  setScrollable: (scrollable: boolean) => void;
};

const ScrollContext = createContext<ScrollContextType | undefined>(undefined);

export function ScrollProvider({ children }: { children: ReactNode }) {
  const [isScrollable, setIsScrollable] = useState(true);

  const setScrollable = (scrollable: boolean) => {
    setIsScrollable(scrollable);
  };

  return (
    <ScrollContext.Provider value={{ isScrollable, setScrollable }}>
      {children}
    </ScrollContext.Provider>
  );
}

export function useScroll() {
  const context = useContext(ScrollContext);
  if (context === undefined) {
    throw new Error('useScroll must be used within a ScrollProvider');
  }
  return context;
}
