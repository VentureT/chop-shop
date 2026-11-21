import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '@venturet/theme';
import App from './App';
import { baseTheme } from './theme';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider defaultTokens={baseTheme} storageKey="chop-shop-theme">
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
