interface LogoProps {
  size?: "sm" | "md" | "lg";
}

export function Logo({ size = "md" }: LogoProps) {
  const sizeClasses = {
    sm: "text-lg",
    md: "text-xl", 
    lg: "text-2xl"
  };

  return (
    <div className={`font-bold ${sizeClasses[size]}`}>
      <span className="text-foreground">Dev</span>
      <span className="text-indigo-500">Forge</span>
    </div>
  );
}
