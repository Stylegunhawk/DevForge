import { createStyles } from 'antd-style';

export const useStyles = createStyles(({ css, token }) => ({
    actions: css`
    display: flex;
    gap: ${token.paddingSM}px;
    justify-content: flex-end;
  `,
    codeEditor: css`
    min-height: 120px;
    border-color: ${token.colorBorderSecondary};
    border-radius: ${token.borderRadius}px;

    font-family: ${token.fontFamilyCode};

    background: ${token.colorFillTertiary};

    &:hover {
      border-color: ${token.colorPrimaryHover} !important;
    }
  `,
    container: css`
    display: flex;
    flex-direction: column;
    gap: ${token.paddingMD}px;

    height: 100%;
    padding-block: ${token.paddingMD}px;
    padding-inline: 0;
  `,
    form: css`
    display: flex;
    flex-direction: column;
    gap: ${token.paddingSM}px;
  `,
    outputContainer: css`
    overflow: auto;
    flex: 1;

    padding: ${token.padding}px;
    border: 1px solid ${token.colorBorder};
    border-radius: ${token.borderRadius}px;

    background: ${token.colorBgContainer};
  `,
}));
