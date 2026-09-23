import type { ReactNode } from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown, ChevronUp } from "lucide-react";

import { cn } from "../../lib/cn";

export interface SelectOption {
  id: string;
  label: string;
}

export function Select<Option extends SelectOption = SelectOption>({
  label,
  value,
  options,
  disabled = false,
  className,
  onChange,
  renderOption,
  renderValue,
}: {
  label: string;
  value: string;
  options: readonly Option[];
  disabled?: boolean;
  className?: string;
  onChange: (value: string) => void;
  renderOption?: (option: Option) => ReactNode;
  renderValue?: (option: Option) => ReactNode;
}) {
  const selectedOption = options.find((option) => option.id === value);

  return (
    <SelectPrimitive.Root value={value} disabled={disabled} onValueChange={onChange}>
      <SelectPrimitive.Trigger className={cn("select-trigger", className)} aria-label={label}>
        <SelectPrimitive.Value>
          {selectedOption && (renderValue ?? renderOption)?.(selectedOption)}
        </SelectPrimitive.Value>
        <SelectPrimitive.Icon asChild><ChevronDown size={14} aria-hidden="true" /></SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content className="select-content" position="popper" sideOffset={5}>
          <SelectPrimitive.ScrollUpButton className="select-scroll-button"><ChevronUp size={13} aria-hidden="true" /></SelectPrimitive.ScrollUpButton>
          <SelectPrimitive.Viewport className="select-viewport">
            {options.map((option) => (
              <SelectPrimitive.Item className="select-item" key={option.id} value={option.id}>
                <SelectPrimitive.ItemText>{renderOption?.(option) ?? option.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="select-item-indicator"><Check size={13} aria-hidden="true" /></SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
          <SelectPrimitive.ScrollDownButton className="select-scroll-button"><ChevronDown size={13} aria-hidden="true" /></SelectPrimitive.ScrollDownButton>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
