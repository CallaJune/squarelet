# Django
# Third Party
# Third Party
from django import forms
from django.core.validators import validate_email
from django.utils.translation import ugettext_lazy as _

# Third Party
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout

# Squarelet
from squarelet.core.forms import StripeForm
from squarelet.core.layout import Field

# Local
from .models import Plan


class UpdateForm(StripeForm):
    """Update an organization"""

    plan = forms.ModelChoiceField(
        label=_("Plan"), queryset=Plan.objects.none(), empty_label=None
    )
    max_users = forms.IntegerField(label=_("Number of Users"), min_value=5)
    private = forms.BooleanField(label=_("Private"), required=False)
    receipt_emails = forms.CharField(
        label=_("Receipt Emails"),
        widget=forms.Textarea(),
        required=False,
        help_text=_("One email address per line"),
    )
    avatar = forms.ImageField(label=_("Avatar"), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_group_options()

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field("stripe_pk"),
            Field("stripe_token"),
            Fieldset("Plan", Field("plan"), css_class="_cls-compactField"),
            Fieldset("Max Users", Field("max_users"), css_class="_cls-compactField")
            if "max_users" in self.fields
            else None,
            Fieldset("Private", Field("private"), css_class="_cls-compactField")
            if "private" in self.fields
            else None,
            Fieldset("Avatar", Field("avatar"), css_class="_cls-compactField"),
            Fieldset(
                "Receipt emails",
                Field("receipt_emails", id="_id-receiptEmails"),
                css_class="_cls-resizeField",
            ),
            Fieldset(
                "Credit card",
                Field("use_card_on_file"),
                css_class="_cls-compactField",
                id="_id-cardFieldset",
            )
            if "use_card_on_file" in self.fields
            else None,
        )
        self.helper.form_tag = False

    def _set_group_options(self):
        # only show public options, plus the current plan, in case they are currently
        # on a private plan, plus private plans they have been given access to
        self.fields["plan"].queryset = Plan.objects.choices(self.organization)
        self.fields["plan"].default = self.organization.plan
        if self.organization.individual:
            del self.fields["max_users"]
            del self.fields["private"]
        else:
            limit_value = max(5, self.organization.user_count())
            self.fields["max_users"].validators[0].limit_value = limit_value
            self.fields["max_users"].widget.attrs["min"] = limit_value
            self.fields["max_users"].initial = limit_value

    def clean_receipt_emails(self):
        """Make sure each line is a valid email"""
        emails = self.cleaned_data["receipt_emails"].split("\n")
        emails = [e.strip() for e in emails if e.strip()]
        bad_emails = []
        for email in emails:
            try:
                validate_email(email.strip())
            except forms.ValidationError:
                bad_emails.append(email)
        if bad_emails:
            raise forms.ValidationError("Invalid email: %s" % ", ".join(bad_emails))
        return emails

    def clean(self):
        data = super().clean()

        payment_required = data["plan"] != self.organization.plan and (
            data["plan"].base_price > 0 or data["plan"].price_per_user > 0
        )
        payment_supplied = data.get("use_card_on_file") or data.get("stripe_token")

        if payment_required and not payment_supplied:
            self.add_error(
                None,
                _("You must supply a credit card number to upgrade to a non-free plan"),
            )

        if "max_users" in data and data["max_users"] < data["plan"].minimum_users:
            self.add_error(
                "max_users",
                _(
                    "The minimum users for the {} plan is {}".format(
                        data["plan"], data["plan"].minimum_users
                    )
                ),
            )

        return data


class AddMemberForm(forms.Form):
    """Add a member to the organization"""

    email = forms.EmailField()
