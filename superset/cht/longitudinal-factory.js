const childLongitudinalTemplate = (form) => {
  // Each form owns its date; every evaluation resets it before checking eligibility.
  let dueDate = null;
  return {
    name: `task.${form}`,
    title: taskTitle(form),
    icon: 'icon-healthcare',
    appliesTo: 'contacts',
    appliesToType: ['c92_household'],
    appliesIf: (contact) => {
      dueDate = null;
      if (!contact || !contact.contact || !isAlive(contact, contact.reports || [])) {
        return false;
      }
      const userRole = user.role;
      if (userRole !== 'chw' && userRole !== 'oca') {
        return false;
      }
      const now = DateTime.now().startOf('day');
      const dateOfBirth = DateTime.fromISO(contact.contact.date_of_birth || '').startOf('day');
      const diff = Interval.fromDateTimes(dateOfBirth, now);
      if (!diff.isValid) {
        return false;
      }
      const nbMonths = Math.round(diff.length('months'));
      if (nbMonths < 1 || nbMonths > 228 || (userRole === 'oca' && nbMonths > 60)) {
        return false;
      }

      let actionForm = '';
      if (nbMonths <= 24) {
        actionForm = Forms.CHILD_LONGITUDINAL_FOLLOWUP_1_24;
      } else if (nbMonths <= 66) {
        actionForm = Forms.CHILD_LONGITUDINAL_FOLLOWUP_2_5;
      } else if (nbMonths >= 72 && nbMonths <= 150) {
        actionForm = Forms.CHILD_LONGITUDINAL_FOLLOWUP_6_12;
      } else if (nbMonths >= 156) {
        actionForm = Forms.CHILD_LONGITUDINAL_FOLLOWUP_13_19;
      }
      if (actionForm !== form) {
        return false;
      }
      const reports = contact.reports || [];
      const relation = contact.contact.relation;
      if (form === Forms.CHILD_LONGITUDINAL_FOLLOWUP_13_19 &&
          (!relation || relation.matrimonial_status !== 'single' || isPregnant(reports))) {
        return false;
      }
      const lastReport = Utils.getMostRecentReport(reports, form);
      if (lastReport && Utils.getField(lastReport, 's_general_info.s_task.task_to_perform') === 'close_followup') {
        return false;
      }

      let scheduledDate = null;
      if (nbMonths <= 24) {
        const chwAges = [1, 3, 6, 9, 12, 18, 24];
        const ages = userRole === 'chw' ? chwAges : Array.from({ length: 24 }, (_, i) => i + 1);
        scheduledDate = ages.map(months => dateOfBirth.plus({ months }))
          .find(birthday => birthday >= now.minus({ days: 2 }) && birthday <= now.plus({ days: 2 }));
      } else if (userRole === 'oca' && lastReport) {
        scheduledDate = getDynamicReportedDate(lastReport).plus({ months: 1 }).startOf('day');
      } else {
        const step = userRole === 'oca' ? 1 : 6;
        // Anchor directly to birth, including leap days and the end of a month.
        let months = Math.floor(diff.length('months') / step) * step;
        scheduledDate = dateOfBirth.plus({ months });
        if (scheduledDate.plus({ days: 2 }) < now) {
          months += step;
          scheduledDate = dateOfBirth.plus({ months });
        }
        // Do not schedule a visit beyond the existing form's age bracket.
        const maxMonths = form === Forms.CHILD_LONGITUDINAL_FOLLOWUP_2_5 ? 66 :
          form === Forms.CHILD_LONGITUDINAL_FOLLOWUP_6_12 ? 150 : 228;
        if (months > maxMonths || (userRole === 'oca' && months > 60)) {
          scheduledDate = null;
        }
      }

      const registration = DateTime.fromMillis(Number(contact.contact.reported_date));
      const daysSinceRegistration = Interval.fromDateTimes(registration, DateTime.now()).length('days');
      if (!lastReport && daysSinceRegistration >= 0 && daysSinceRegistration <= 2) {
        scheduledDate = registration;
      }
      if (!scheduledDate || !scheduledDate.isValid) {
        return false;
      }
      dueDate = scheduledDate.toJSDate();
      return true;
    },
    actions: [{ form }],
    events: [{ id: form, dueDate: () => dueDate, start: 2, end: 2 }]
  };
};