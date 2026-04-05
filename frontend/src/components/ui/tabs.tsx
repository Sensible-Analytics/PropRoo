import React, { createContext, useContext, useState, type ReactNode } from 'react';

interface TabsContextType {
  value: string;
  onChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextType>({ value: '', onChange: () => {} });

export function Tabs({ children, defaultValue, value, onValueChange }: {
  children: ReactNode;
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}) {
  const [internalValue, setInternalValue] = useState(defaultValue || '');
  const currentValue = value ?? internalValue;
  const handleChange = onValueChange ?? setInternalValue;

  return (
    <TabsContext.Provider value={{ value: currentValue, onChange: handleChange }}>
      <div>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`flex gap-1 p-1 bg-slate-800 rounded-lg ${className}`}>{children}</div>;
}

export function TabsTrigger({ children, value, className = '' }: { children: ReactNode; value: string; className?: string }) {
  const { value: currentValue, onChange } = useContext(TabsContext);
  const isActive = currentValue === value;

  return (
    <button
      onClick={() => onChange(value)}
      className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all ${
        isActive ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
      } ${className}`}
    >
      {children}
    </button>
  );
}

export function TabsContent({ children, value, className = '' }: { children: ReactNode; value: string; className?: string }) {
  const { value: currentValue } = useContext(TabsContext);
  if (currentValue !== value) return null;
  return <div className={className}>{children}</div>;
}
