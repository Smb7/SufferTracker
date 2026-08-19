import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';
import { AppShellComponent } from './layout/app-shell.component';
import { LoginComponent } from './pages/login.component';
import { DashboardComponent } from './pages/dashboard.component';
import { JobsComponent } from './pages/jobs.component';
import { SettingsComponent } from './pages/settings.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: '', component: AppShellComponent, canActivate: [authGuard], children: [
    { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    { path: 'dashboard', component: DashboardComponent },
    { path: 'jobs', component: JobsComponent },
    { path: 'settings', component: SettingsComponent }
  ]},
  { path: '**', redirectTo: '' }
];
