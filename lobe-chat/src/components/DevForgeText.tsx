import React, { FC } from 'react';


const DevForgeText: FC<{ style?: React.CSSProperties }> = ({ style }) => (
  <span style={{ fontSize: 18, fontWeight: 700, ...style }}>
    Dev<span style={{ color: '#00BFFF' }}>Forge</span>
  </span>
);

export default DevForgeText;
