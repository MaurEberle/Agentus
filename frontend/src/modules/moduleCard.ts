/** Hard cap: no dashboard / monitoring / history card grows past 1000px. */
export const MODULE_MAX_H = 'max-h-[1000px]';
export const moduleCardClass = `flex ${MODULE_MAX_H} min-h-0 flex-col overflow-hidden`;
export const moduleCardTallClass = moduleCardClass;
export const moduleCardBodyClass = 'min-h-0 flex-1 overflow-x-hidden overflow-y-auto';
/** React Flow and split panes need a definite height, still capped at 1000px. */
export const modulePaneHeightClass = 'h-[min(1000px,70vh)] min-h-[16rem]';
