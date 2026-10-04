import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/source-sans-3';
import './ui/tokens.css';
import './ui/styles.css';
import './shell/shell.css';
import { App } from './shell/App';

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
