export function resumeFields(profile, field, area) {
  return field('Роли в команде', 'roles', profile.roles, 'text', 'maxlength="2000"')
    + field('Стаж и опыт работы', 'experience', profile.experience, 'text', 'maxlength="2000"')
    + area('Навыки общения и работы в команде', 'soft_skills', profile.soft_skills);
}

export function resumeDetails(profile, escape) {
  return [
    ['Роли', profile.roles],
    ['Стаж и опыт', profile.experience],
    ['Работа в команде', profile.soft_skills],
  ].filter(([, value]) => value)
    .map(([label, value]) => `<p><strong>${label}:</strong> ${escape(value)}</p>`).join('');
}
