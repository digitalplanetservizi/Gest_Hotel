import tseslint from 'typescript-eslint';
import angular from 'angular-eslint';

export default tseslint.config(
 { ignores:['dist/**','node_modules/**','.angular/**'] },
 {
  files:['src/**/*.ts'],
  extends:[...tseslint.configs.recommended,...angular.configs.tsRecommended],
  processor:angular.processInlineTemplates,
  rules:{ '@angular-eslint/prefer-inject':'error' }
 },
 {
  files:['**/*.html'],
  extends:[...angular.configs.templateRecommended,...angular.configs.templateAccessibility],
  rules:{ '@angular-eslint/template/no-any':'off' }
 }
);
