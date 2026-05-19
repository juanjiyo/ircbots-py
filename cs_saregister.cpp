/* cs_saregister - ChanServ SAREGISTER module for Anope 2.0
 *
 * Allows services admins with chanserv/saregister permission
 * to register a channel without being in it.
 *
 * Based on ns_saregister by Maxwell175 and cs_register by Anope Team.
 */

#include "module.h"

class CommandCSSARegister : public Command
{
 public:
	CommandCSSARegister(Module *creator) : Command(creator, "chanserv/saregister", 1, 2)
	{
		this->SetDesc(_("Force register a channel"));
		this->SetSyntax(_("\037channel\037 [\037description\037]"));
	}

	void Execute(CommandSource &source, const std::vector<Anope::string> &params) anope_override
	{
		const Anope::string &chan = params[0];
		const Anope::string &chdesc = params.size() > 1 ? params[1] : "";
		unsigned maxregistered = Config->GetModule("chanserv")->Get<unsigned>("maxregistered");

		User *u = source.GetUser();
		NickCore *nc = source.nc;
		ChannelInfo *ci = ChannelInfo::Find(params[0]);

		if (Anope::ReadOnly)
			source.Reply(_("Sorry, channel registration is temporarily disabled."));
		else if (nc->HasExt("UNCONFIRMED"))
			source.Reply(_("You must confirm your account before you can register a channel."));
		else if (chan[0] == '&')
			source.Reply(_("Local channels cannot be registered."));
		else if (chan[0] != '#')
			source.Reply(CHAN_SYMBOL_REQUIRED);
		else if (!IRCD->IsChannelValid(chan))
			source.Reply(CHAN_X_INVALID, chan.c_str());
		else if (ci)
			source.Reply(_("Channel \002%s\002 is already registered!"), chan.c_str());
		else if (maxregistered && nc->channelcount >= maxregistered && !source.HasPriv("chanserv/no-register-limit"))
			source.Reply(nc->channelcount > maxregistered ? CHAN_EXCEEDED_CHANNEL_LIMIT : CHAN_REACHED_CHANNEL_LIMIT, maxregistered);
		else
		{
			ci = new ChannelInfo(chan);
			ci->SetFounder(nc);
			ci->desc = chdesc;

			ci->last_topic_setter = source.service->nick;

			Log(LOG_COMMAND, source, this, ci);
			source.Reply(_("Channel \002%s\002 registered under your account: %s"), chan.c_str(), nc->display.c_str());

			FOREACH_MOD(OnChanRegistered, (ci));

			Channel *c = Channel::Find(params[0]);
			if (c)
			{
				c->CheckModes();
			}
		}
	}

	bool OnHelp(CommandSource &source, const Anope::string &subcommand) anope_override
	{
		this->SendSyntax(source);
		source.Reply(" ");
		source.Reply(_("This module lets a services operator with the\n"
				"chanserv/saregister privileges register a\n"
				"channel without being in it.\n"
				"The channel does not need to exist yet."));
		return true;
	}
};

class CSSARegister : public Module
{
	CommandCSSARegister commandcssaregister;

 public:
	CSSARegister(const Anope::string &modname, const Anope::string &creator) : Module(modname, creator, THIRD),
		commandcssaregister(this)
	{
		this->SetAuthor("ircbots");
	}
};

MODULE_INIT(CSSARegister)
