// Issue #9.2:Enhancement - To disable scrolling on numeric textfields
// This reuses TextWidget component from RJSF, with minor changes to obtain the desired requirement
import React from "react"
import { WidgetProps, utils } from "@rjsf/core"
import TextField from "@mui/material/TextField"

const { getDisplayLabel } = utils

const CustomTextWidget = ({
    id,
    placeholder,
    required,
    readonly,
    disabled,
    type,
    label,
    value,
    onChange,
    onBlur,
    onFocus,
    autofocus,
    options,
    schema,
    uiSchema,
    rawErrors = [],
    formContext,
    registry,
}: WidgetProps) => {
    const _onChange = ({ target: { value } }: React.ChangeEvent<HTMLInputElement>) =>
        onChange(value === "" ? options.emptyValue : value)
    const _onBlur = ({ target: { value } }: React.FocusEvent<HTMLInputElement>) =>
        onBlur(id, value)
    const _onFocus = ({ target: { value } }: React.FocusEvent<HTMLInputElement>) =>
        onFocus(id, value)

    const { rootSchema } = registry
    const displayLabel = getDisplayLabel(schema, uiSchema, rootSchema)

    // Input fields type is set to 'text', while an additional prop describing the inputMode,
    // which is set to 'numeric', helps remove the up-down button, and disable scroll-based change of value of the input field
    return (
        <TextField
            id={id}
            placeholder={placeholder}
            label={displayLabel ? label || schema.title : false}
            autoFocus={autofocus}
            required={required}
            disabled={disabled || readonly}
            type="text"
            inputProps={{ inputMode: "numeric" }}
            value={value || value === 0 ? value : ""}
            error={rawErrors.length > 0}
            variant="standard"
            onChange={_onChange}
            onBlur={_onBlur}
            onFocus={_onFocus}
        />
    )
}

export default CustomTextWidget
