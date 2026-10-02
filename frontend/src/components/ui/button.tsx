import type { ButtonHTMLAttributes, PropsWithChildren } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/cn";

const buttonVariants = cva("button", {
  variants: {
    variant: { primary: "button-primary", quiet: "", danger: "button-danger" },
  },
  defaultVariants: { variant: "quiet" },
});

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, children, ...props }: PropsWithChildren<ButtonProps>) {
  return <button className={cn(buttonVariants({ variant }), className)} {...props}>{children}</button>;
}
